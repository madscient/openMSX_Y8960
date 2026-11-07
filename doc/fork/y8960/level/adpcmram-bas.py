"""FS-CA1 の ADPCM の RAM を、実機の MSX から probe-y8950-adpcm-ram.ps1 と同じ手順で読み書きする BASIC を作る。

    python adpcmram-bas.py            # 同じディレクトリに adpcmram.bas（ASCII、CRLF）を書く
    python adpcmram-bas.py --list     # 機械語の番地と命令の対応も出す

MSX での使い方: RUN して、08h に書く値（0 か 2）と、旧手順に戻す違いの頭文字（M・O・H・E を並べる。空なら戻さない）を
答える。意味は probe-y8950-adpcm-ram.ps1 の -R08 と -Revert と同じ。終わったら MSX をリセットする（フラグをすべてマスクして返る）。
表示は試験ごとに 2 行。W は書き、R は読み。D はダミーの 2 回、G はその後の 4 回、OK/NG は書いた値と合ったか、
A は 4 バイトの後の状態。RD は各バイトの前の BUF_RDY の待ち（最初の状態>最後の状態/読んだ回数。T は打ち切り。- は待っていない）、
PS は各バイトの直後で 04h=80h より前の状態。最後の MATCH は合ったバイトの数。

MGA の版との違い: 始める前にチップをリセットしない（MGA は SRST を挟む）。C0h が閉じているときだけ、"AUDIO" の印があるスロットの
7FFFh に 01h を書く（MGA は毎回書く）。

Y8950 を触る部分は機械語にして、割り込みを止めて走らせる。メモリのモードで 04h=00h にすると状態の IRQ が立ちっぱなしになり、
IRQ が /INT に繋がっていれば BASIC は割り込みから戻れなくなる（openMSX では、BASIC から直接書いた形が止まった。
実機の FS-CA1 の配線は確かめていない）。割り込みの処理が C0h を触れば、レジスタの番地もずれる。
各 I/O の後には待ちを入れ、MGA の 1 コマンドの間隔（平均 1.37ms）にそろえる。
BASIC の行は MSX の文字で表示されるので、REM と表示は ASCII だけで書く。
"""
import os
import re
import sys

ORG = 0xC000
PB = 0xC300
BUF = 0xC400
# MGA の 1 コマンドの間隔にそろえる待ちのループ回数。openMSX の HB-F1XDJ（Z80 3.58MHz）で 1 回の I/O あたり 1.376ms になった。
# CPU が速い機種（turbo R の R800）では待ちが短くなる（未確認）
DELAY = 159

EQU = {
    'R08': PB + 0, 'MASKV': PB + 1, 'ENDV': PB + 2, 'FLAGS': PB + 3, 'DLYCNT': PB + 4,
    'NTEST': PB + 6, 'SLOTID': PB + 7, 'VAL7F': PB + 8, 'RADDR': PB + 9, 'RVAL': PB + 11,
    'TABLE': PB + 16, 'CNT': PB + 32, 'VBASE': PB + 33, 'MODE': PB + 34,
    'BUF': BUF, 'RDSLT': 0x000C, 'WRSLT': 0x0014, 'PADR': 0xC0, 'PDAT': 0xC1,
}

SOURCE = r"""
; 入口の表。BASIC は USR=ORG（MAIN）、USR1=ORG+3（OPEN）、USR2=ORG+6（PEEKS）で呼ぶ
        JP MAIN
        JP OPEN
        JP PEEKS

; OPEN: スロット SLOTID の 7FFFh に VAL7F を書く（FS-CA1 は bit0 で C0h/C1h を開く）
OPEN:   LD A,(VAL7F)
        LD E,A
        LD A,(SLOTID)
        LD HL,7FFFH
        CALL WRSLT
        EI
        RET

; PEEKS: スロット SLOTID の番地 RADDR を読んで RVAL に置く
PEEKS:  LD A,(SLOTID)
        LD HL,(RADDR)
        CALL RDSLT
        LD (RVAL),A
        EI
        RET

; MAIN: 書きの試験を NTEST 回、続けて読みの試験を NTEST 回。結果は BUF から 24 バイトずつ
;   +0,+1  ダミーの 2 回の読み（読みの試験だけ）
;   +2+5*i バイト i（0..3）ごとに 5 バイト: 待ちの最初の状態、最後の状態、読んだ回数（0 は待っていない、bit7 は打ち切り）、
;          直後の状態（04h=80h より前）、読んだデータ（読みの試験だけ）
;   +22    4 バイトの後の状態
; HL は BUF の書き込み位置、IX は TABLE の位置として全体で持ち回る
MAIN:   DI
        PUSH IX
        LD HL,BUF
        LD IX,TABLE
        LD A,(NTEST)
        LD (CNT),A
        LD A,10H
        LD (VBASE),A
WT:     LD A,60H
        CALL SETUP
        XOR A
        LD (HL),A
        INC HL
        LD (HL),A
        INC HL
        LD A,(VBASE)
        LD C,A
        LD B,4
        LD A,(FLAGS)
        BIT 1,A
        JR Z,WTM
; Handshake を戻した形: 0Fh を 1 回だけ選び、書くたびに状態を読む
        LD A,0FH
        CALL WRA
WTH:    XOR A
        LD (HL),A
        INC HL
        LD (HL),A
        INC HL
        LD (HL),A
        INC HL
        INC C
        LD A,C
        CALL WRD
        CALL RDS
        LD (HL),A
        INC HL
        LD (HL),0
        INC HL
        DJNZ WTH
        JR WTE
; マニュアルの形: BUF_RDY を待ち、0Fh を選んで書き、状態を読み、04h=80h
WTM:    CALL WAITRDY
        LD A,0FH
        CALL WRA
        INC C
        LD A,C
        CALL WRD
        CALL RDS
        LD (HL),A
        INC HL
        LD (HL),0
        INC HL
        LD DE,0480H
        CALL YWR
        DJNZ WTM
WTE:    CALL TAIL
        LD A,(VBASE)
        ADD A,10H
        LD (VBASE),A
        LD A,(CNT)
        DEC A
        LD (CNT),A
        JP NZ,WT

        LD IX,TABLE
        LD A,(NTEST)
        LD (CNT),A
RT:     LD A,20H
        CALL SETUP
        LD A,0FH
        CALL WRA
        CALL RDD
        LD (HL),A
        INC HL
        CALL RDD
        LD (HL),A
        INC HL
        LD B,4
        LD A,(FLAGS)
        BIT 1,A
        JR Z,RTM
RTH:    XOR A
        LD (HL),A
        INC HL
        LD (HL),A
        INC HL
        LD (HL),A
        INC HL
        CALL RDD
        LD E,A
        CALL RDS
        LD (HL),A
        INC HL
        LD (HL),E
        INC HL
        DJNZ RTH
        JR RTE
RTM:    CALL WAITRDY
        LD A,0FH
        CALL WRA
        CALL RDD
        LD E,A
        CALL RDS
        LD (HL),A
        INC HL
        LD (HL),E
        INC HL
        LD DE,0480H
        CALL YWR
        DJNZ RTM
RTE:    CALL TAIL
        LD A,(CNT)
        DEC A
        LD (CNT),A
        JP NZ,RT

; 割り込みを戻す前に、フラグをすべてマスクして IRQ を消す。残すと EI の直後に IRQ が MSX に渡る
        LD DE,0478H
        CALL YWR
        LD DE,0480H
        CALL YWR
        POP IX
        EI
        RET

; TAIL: 4 バイトの後の状態と詰め物を HL に置き、07h=ENDV を書き、IX を次の試験に進める。壊す: A, DE
TAIL:   CALL RDS
        LD (HL),A
        INC HL
        LD (HL),0
        INC HL
        LD D,07H
        LD A,(ENDV)
        LD E,A
        CALL YWR
        INC IX
        INC IX
        RET

; SETUP: 入口 A = 07h に書くモード。IX の試験の番地を使う。壊す: A, DE
; マニュアルの順: 04h=MASKV、04h=80h、07h=モード、08h、09h-0Ch
; Order を戻した順: 07h=01h、08h、04h=MASKV、09h-0Ch、07h=モード、04h=80h
SETUP:  LD (MODE),A
        LD A,(FLAGS)
        BIT 0,A
        JR Z,SUM
        LD DE,0701H
        CALL YWR
        CALL S08
        CALL S04
        CALL SADR
        CALL S07
        LD DE,0480H
        JR YWR
SUM:    CALL S04
        LD DE,0480H
        CALL YWR
        CALL S07
        CALL S08
        JR SADR
S04:    LD D,04H
        LD A,(MASKV)
        JR SDV
S07:    LD D,07H
        LD A,(MODE)
        JR SDV
S08:    LD D,08H
        LD A,(R08)
SDV:    LD E,A
        JR YWR
; 4 バイトは 1 つのブロックに収まるので、停止の番地は開始と同じ
SADR:   LD D,09H
        LD E,(IX+0)
        CALL YWR
        LD D,0AH
        LD E,(IX+1)
        CALL YWR
        LD D,0BH
        LD E,(IX+0)
        CALL YWR
        LD D,0CH
        LD E,(IX+1)
        JR YWR

; WAITRDY: BUF_RDY（状態の bit3）が立つまで状態を最大 30 回読む。HL に 最初の状態・最後の状態・回数 を置いて HL+=3
; 打ち切りなら回数の bit7 を立てる。壊す: A。BC は保つ
WAITRDY: PUSH BC
        LD B,30
        LD C,0
        CALL RDS
        LD (HL),A
WR1:    INC C
        BIT 3,A
        JR NZ,WR3
        DEC B
        JR Z,WR2
        CALL RDS
        JR WR1
WR2:    SET 7,C
WR3:    INC HL
        LD (HL),A
        INC HL
        LD (HL),C
        INC HL
        POP BC
        RET

; YWR: レジスタ D に E を書く。壊す: A
YWR:    LD A,D
        CALL WRA
        LD A,E
        JR WRD

; 1 回の I/O と、その後の待ち。RDS と RDD は A に読んだ値を返す。A 以外は保つ
WRA:    OUT (PADR),A
        JR DLY
WRD:    OUT (PDAT),A
        JR DLY
RDS:    IN A,(PADR)
        JR DLY
RDD:    IN A,(PDAT)
; DLY: DLYCNT 回のループで待つ。全レジスタとフラグを保つ。DLYCNT は 1 以上
DLY:    PUSH AF
        PUSH BC
        LD BC,(DLYCNT)
DLY1:   DEC BC
        LD A,B
        OR C
        JR NZ,DLY1
        POP BC
        POP AF
        RET
"""

R8 = {'B': 0, 'C': 1, 'D': 2, 'E': 3, 'H': 4, 'L': 5, '(HL)': 6, 'A': 7}
R16 = {'BC': 0x00, 'DE': 0x10, 'HL': 0x20}
PUSHPOP = {'BC': 0xC0, 'DE': 0xD0, 'HL': 0xE0, 'AF': 0xF0}
CC = {'NZ': 0, 'Z': 1, 'NC': 2, 'C': 3}


def value(expr, labels):
    e = re.sub(r'\b([0-9][0-9A-F]*)H\b', lambda m: str(int(m.group(1), 16)), expr)
    return eval(e, {'__builtins__': {}}, labels)


def encode(op, pc, labels, final):
    """1 命令を機械語にする。final が偽の間は、未定義のラベルを 0 として大きさだけを決める"""
    def v(x):
        try:
            return value(x, labels)
        except NameError:
            if final:
                raise
            return 0

    def w(x):
        n = v(x) & 0xFFFF
        return [n & 0xFF, n >> 8]

    def rel(x):
        d = v(x) - (pc + 2)
        if final and not -128 <= d <= 127:
            raise ValueError(f'JR out of range: {op}')
        return d & 0xFF

    fixed = {'DI': [0xF3], 'EI': [0xFB], 'RET': [0xC9], 'XOR A': [0xAF], 'OR C': [0xB1],
             'PUSH IX': [0xDD, 0xE5], 'POP IX': [0xDD, 0xE1], 'INC IX': [0xDD, 0x23],
             'INC HL': [0x23], 'DEC BC': [0x0B]}
    if op in fixed:
        return fixed[op]
    m = re.fullmatch(r'(PUSH|POP) (BC|DE|HL|AF)', op)
    if m:
        return [PUSHPOP[m.group(2)] + (5 if m.group(1) == 'PUSH' else 1)]
    m = re.fullmatch(r'(INC|DEC) (B|C|D|E|H|L|A)', op)
    if m:
        return [(4 if m.group(1) == 'INC' else 5) + 8 * R8[m.group(2)]]
    m = re.fullmatch(r'LD (B|C|D|E|H|L|A|\(HL\)),(B|C|D|E|H|L|A|\(HL\))', op)
    if m and op != 'LD (HL),(HL)':
        return [0x40 + 8 * R8[m.group(1)] + R8[m.group(2)]]
    m = re.fullmatch(r'LD (B|C|D|E|H|L|A),\(IX\+(.+)\)', op)
    if m:
        return [0xDD, 0x46 + 8 * R8[m.group(1)], v(m.group(2)) & 0xFF]
    m = re.fullmatch(r'LD A,\((.+)\)', op)
    if m:
        return [0x3A] + w(m.group(1))
    m = re.fullmatch(r'LD \((.+)\),A', op)
    if m:
        return [0x32] + w(m.group(1))
    m = re.fullmatch(r'LD BC,\((.+)\)', op)
    if m:
        return [0xED, 0x4B] + w(m.group(1))
    m = re.fullmatch(r'LD HL,\((.+)\)', op)
    if m:
        return [0x2A] + w(m.group(1))
    m = re.fullmatch(r'LD (BC|DE|HL),(.+)', op)
    if m:
        return [0x01 + R16[m.group(1)]] + w(m.group(2))
    m = re.fullmatch(r'LD IX,(.+)', op)
    if m:
        return [0xDD, 0x21] + w(m.group(1))
    m = re.fullmatch(r'LD (B|C|D|E|H|L|A|\(HL\)),(.+)', op)
    if m:
        return [0x06 + 8 * R8[m.group(1)], v(m.group(2)) & 0xFF]
    m = re.fullmatch(r'ADD A,(.+)', op)
    if m:
        return [0xC6, v(m.group(1)) & 0xFF]
    m = re.fullmatch(r'(BIT|SET) ([0-7]),(B|C|D|E|H|L|A)', op)
    if m:
        return [0xCB, (0x40 if m.group(1) == 'BIT' else 0xC0) + 8 * int(m.group(2)) + R8[m.group(3)]]
    m = re.fullmatch(r'OUT \((.+)\),A', op)
    if m:
        return [0xD3, v(m.group(1)) & 0xFF]
    m = re.fullmatch(r'IN A,\((.+)\)', op)
    if m:
        return [0xDB, v(m.group(1)) & 0xFF]
    m = re.fullmatch(r'JR (NZ|Z|NC|C),(.+)', op)
    if m:
        return [0x20 + 8 * CC[m.group(1)], rel(m.group(2))]
    m = re.fullmatch(r'JR (.+)', op)
    if m:
        return [0x18, rel(m.group(1))]
    m = re.fullmatch(r'DJNZ (.+)', op)
    if m:
        return [0x10, rel(m.group(1))]
    m = re.fullmatch(r'JP (NZ|Z|NC|C),(.+)', op)
    if m:
        return [0xC2 + 8 * CC[m.group(1)]] + w(m.group(2))
    m = re.fullmatch(r'JP (.+)', op)
    if m:
        return [0xC3] + w(m.group(1))
    m = re.fullmatch(r'CALL (.+)', op)
    if m:
        return [0xCD] + w(m.group(1))
    raise ValueError(f'unknown instruction: {op}')


def assemble(src):
    lines = []
    for raw in src.splitlines():
        code = raw.split(';', 1)[0].rstrip()
        if not code.strip():
            continue
        label = None
        m = re.match(r'^([A-Z][A-Z0-9]*):\s*(.*)$', code)
        if m:
            label, code = m.group(1), m.group(2)
        op = re.sub(r'\s+', ' ', code.strip())
        op = re.sub(r'\s*,\s*', ',', op)
        lines.append((label, op))
    labels = dict(EQU)
    for final in (False, True):
        pc = ORG
        out = []
        listing = []
        for label, op in lines:
            if label:
                if not final and label in labels:
                    raise ValueError(f'duplicate label: {label}')
                labels[label] = pc
            if not op:
                continue
            b = encode(op, pc, labels, final)
            listing.append((pc, b, (label + ': ' if label else '') + op))
            out += b
            pc += len(b)
    return out, labels, listing


BASIC = r"""
10 REM Y8950 ADPCM RAM PROBE FOR FS-CA1
20 REM SAME STEPS AS PROBE-Y8950-ADPCM-RAM.PS1
30 CLEAR 200,&HBFFF:DEFINT A-Z:DIM T$(6)
40 SCREEN 0:WIDTH 40:KEY OFF
50 MB=&H{ORG:04X}:PB=&H{PB:04X}:BF=&H{BUF:04X}
60 DEF FNH$(X)=RIGHT$("0"+HEX$(X),2)
70 GOSUB 900
80 DEFUSR=MB:DEFUSR1=MB+3:DEFUSR2=MB+6
100 INPUT "08H (0/2)";R8:IF R8<>0 AND R8<>2 THEN 100
110 INPUT "REVERT (M,O,H,E)";R$
120 DL={DELAY}
130 M=INSTR(R$,"M")+INSTR(R$,"m")>0:O=INSTR(R$,"O")+INSTR(R$,"o")>0
140 H=INSTR(R$,"H")+INSTR(R$,"h")>0:E=INSTR(R$,"E")+INSTR(R$,"e")>0
150 POKE PB,R8:POKE PB+1,120 AND M:POKE PB+2,1 AND E
160 POKE PB+3,(1 AND O) OR (2 AND H):POKE PB+4,DL AND 255:POKE PB+5,DL\256
170 N=0:RESTORE 1100
180 FOR I=1 TO 6:READ A$,B$:B=VAL("&H"+B$)
190 IF (R8 AND 2)<>0 AND (B AND &H1008)<>0 THEN 210
200 N=N+1:T$(N)=A$:POKE PB+14+2*N,B AND 255:POKE PB+15+2*N,(B AND &HFF00)\256 AND 255
210 NEXT:POKE PB+6,N
300 S=INP(&HC0):PRINT "C0H AT START: ";FNH$(S)
310 IF S<>255 THEN 400
320 GOSUB 1000:IF SI<0 THEN PRINT "FS-CA1 (AUDIO) NOT FOUND":END
330 POKE PB+7,SI:POKE PB+8,1:A=USR1(0):S=INP(&HC0)
340 PRINT "7FFFH=01 IN SLOT ";FNH$(SI);", C0H: ";FNH$(S)
350 IF S=255 THEN PRINT "C0H/C1H STILL CLOSED":END
400 GOSUB 850:A=USR(0):OK=0
500 FOR I=0 TO 2*N-1:J=I MOD N+1:R=BF+24*I
510 IF I=N THEN GOSUB 800
520 IF I<N THEN L$="W " ELSE L$="R "
530 L$=L$+T$(J)
540 IF I<N THEN FOR K=0 TO 3:L$=L$+" "+FNH$(16*J+K+1):NEXT:GOTO 580
550 L$=L$+" D:"+FNH$(PEEK(R))+" "+FNH$(PEEK(R+1))+" G:":C=0
560 FOR K=0 TO 3:V=PEEK(R+6+5*K):L$=L$+FNH$(V)+" ":C=C-(V=16*J+K+1):NEXT
570 OK=OK+C:IF C=4 THEN L$=L$+"OK" ELSE L$=L$+"NG"
580 PRINT L$;" A:";FNH$(PEEK(R+22))
590 L$=" RD":FOR K=0 TO 3:G=R+2+5*K:GOSUB 700:NEXT
600 L$=L$+" PS":FOR K=0 TO 3:L$=L$+" "+FNH$(PEEK(R+5+5*K)):NEXT
610 PRINT L$:NEXT
620 PRINT "MATCH";OK;"/";4*N
630 PRINT "RESET THE MSX BEFORE USING FS-CA1"
640 END
700 C=PEEK(G+2):IF C=0 THEN L$=L$+" -":RETURN
710 L$=L$+" "+FNH$(PEEK(G)):IF PEEK(G)<>PEEK(G+1) THEN L$=L$+">"+FNH$(PEEK(G+1))
720 L$=L$+"/"+MID$(STR$(C AND 127),2):IF C AND 128 THEN L$=L$+"T"
730 RETURN
800 PRINT "HIT ANY KEY";:A$=INPUT$(1):CLS:GOSUB 850:RETURN
850 PRINT "08H=";FNH$(R8);" 04H=";FNH$(PEEK(PB+1));" END 07H=";FNH$(PEEK(PB+2));" DL=";DL
860 PRINT "REVERT:";:IF M THEN PRINT " MASK";
870 IF O THEN PRINT " ORDER";
880 IF H THEN PRINT " HANDSHAKE";
890 IF E THEN PRINT " END";
895 IF M+O+H+E=0 THEN PRINT " NONE";
897 PRINT:RETURN
900 RESTORE 2000:A=MB:LN=2000
910 READ D$:IF D$="*" THEN RETURN
920 READ CS:S=0:FOR K=1 TO LEN(D$) STEP 2:V=VAL("&H"+MID$(D$,K,2)):POKE A,V:A=A+1:S=S+V:NEXT
930 IF (S AND 255)<>CS THEN PRINT "DATA ERROR IN LINE";LN:END
940 LN=LN+10:GOTO 910
1000 SI=-1:FOR P=0 TO 3:X=PEEK(&HFCC1+P) AND 128
1010 FOR Q=0 TO 3*(X\128):Z=P:IF X THEN Z=128+P+4*Q
1020 W$="":FOR K=0 TO 4:POKE PB+7,Z:POKE PB+9,128+K:POKE PB+10,0:A=USR2(0):W$=W$+CHR$(PEEK(PB+11)):NEXT
1030 IF W$="AUDIO" THEN SI=Z:RETURN
1040 NEXT Q,P:RETURN
1100 DATA 00000,0000,07FFC,1FFF,08000,2000,10000,4000,20000,8000,3FFFC,FFFF
"""

PER_LINE = 24


def main():
    code, labels, listing = assemble(SOURCE)
    assert labels['OPEN'] == ORG + 9 and code[3] == 0xC3 and code[6] == 0xC3
    assert ORG + len(code) <= PB, 'machine code overlaps the parameter block'
    assert EQU['MODE'] < BUF and BUF + 24 * 12 <= 0x10000
    if '--list' in sys.argv:
        for pc, b, text in listing:
            print(f'{pc:04X}  {" ".join(f"{x:02X}" for x in b):<12}  {text}')
        print(f'{len(code)} bytes')
    text = BASIC.strip('\n').replace('{ORG:04X}', f'{ORG:04X}').replace('{PB:04X}', f'{PB:04X}') \
        .replace('{BUF:04X}', f'{BUF:04X}').replace('{DELAY}', str(DELAY))
    out = text.split('\n')
    n = 2000
    for i in range(0, len(code), PER_LINE):
        chunk = code[i:i + PER_LINE]
        out.append(f'{n} DATA {"".join(f"{x:02X}" for x in chunk)},{sum(chunk) & 0xFF}')
        n += 10
    out.append(f'{n} DATA *')
    for line in out:
        assert len(line) < 250 and all(32 <= ord(c) < 127 for c in line), line
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'adpcmram.bas')
    with open(path, 'wb') as f:
        f.write(('\r\n'.join(out) + '\r\n').encode('ascii'))
    print(f'wrote {path}: {len(out)} lines, {len(code)} bytes of machine code')


if __name__ == '__main__':
    main()
