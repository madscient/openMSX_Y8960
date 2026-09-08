# ビルド環境

upstream の一般的な手順は `doc/manual/compile.html` の 5章
"Stand-alone Binary" にある。本書はそこに書かれていない、
**実際にビルドしたマシンの事情と、そこで詰まった点の記録**である。

ビルド実績のあるマシンを OS の版で呼び分ける。**どちらの記述も
そのマシンで実際に踏んだことの記録**であって、一般則ではない。
新しいマシンで始めるときは §5 を見ること。

| 呼び名 | OS |
|---|---|
| **Win11 機** | Windows 11 Pro 26200 / x64 |
| **Win10 機** | Windows 10 Pro 19045 / x64 |

## 1. 環境（すべて確認済み）

### 1.1 Win11 機（2026-09-08 時点）

| 項目 | 値 | 確認方法 |
|---|---|---|
| Visual Studio | Community 2026 (18.x) / `C:\Program Files\Microsoft Visual Studio\18\Community` | `vswhere -all -property installationPath` |
| （同上） | Professional 2019 も入っているが **openMSX には使えない**（v142 は C++23 非対応） | 同上 |
| MSBuild | 18.9.1.35102 / `...\18\Community\MSBuild\Current\Bin\MSBuild.exe` | `MSBuild.exe -version` |
| 利用可能な PlatformToolset (x64) | **v145 と ClangCL のみ** | `MSBuild\Microsoft\VC\v180\Platforms\x64\PlatformToolsets` を列挙 |
| MSVC ツールチェイン | 14.44.35207 / 14.51.36231 / 14.52.36615 | `VC\Tools\MSVC` を列挙 |
| Python | 3.13.15 (`py` の既定) と 3.8.2 が併存 | `py -0p` |

### 1.2 Win10 機（2026-09-09 時点）

| 項目 | 値 | 確認方法 |
|---|---|---|
| Visual Studio | Community 2026 (18.x) と **Community 2022 (17.x) が併存** | `vswhere -all -property installationPath` |
| MSBuild | 18.8.2.30814（VS18）/ 17.14.51.32402（VS2022） | `MSBuild.exe -version` |
| 利用可能な PlatformToolset (x64) | VS18 が **v145 / ClangCL**、VS2022 が **v143** | `MSBuild\Microsoft\VC\v1*\Platforms\x64\PlatformToolsets` を列挙 |
| MSVC ツールチェイン | 14.51.36231（VS18）/ 14.44.35207（VS2022） | `VC\Tools\MSVC` を列挙 |
| Python | 3.13.14 が `py` の既定。3.9（VS 同梱）も在るが既定ではない | `py -0p` |

**各 MSBuild は自分の VS の PlatformToolset しか見えない。** v143 を使うなら
VS2022 の MSBuild を、v145 を使うなら VS18 の MSBuild を呼ぶ。

Win10 機では **v145 を選んだ**（VS18 の MSBuild + `-p:PlatformToolset=v145`）。
v143 も使えるので `-p:PlatformToolset` 無しでも通る見込みだが、そちらは
**試していない**。理由は、Win11 機で実証済みの構成に揃えて手順を 1 本に保つと、
ビルドが失敗したときに疑う先がツールチェインに散らないこと。
**前提**: v145 でこのコードが通る限り成立する。やり直しの値段はビルド時間だけ
（§6 の実測）で、文書もコードも波及しない。

## 2. 詰まりどころ

### 2.1 Python 3.8 では 3rdparty のダウンロードが落ちる（Win11 機）

`build/extract.py:46` が `Path.is_relative_to` を使っている。これは
**Python 3.9 以降**の API で、3.8.2 では `AttributeError` になる
（**確認済み**: 実際に走らせて再現）。

openMSX のビルドスクリプト群のうち 3.9 以降を要求するのは**この 1 か所だけ**
（**確認済み**: `build/*.py` と `build/msvc/*.py` を 3.8 で構文チェックし、
新しい API の使用箇所を grep）。

対処として **Python 3.13.15 を追加インストール**した
（`winget install Python.Python.3.13`）。これにより `py` ランチャの既定が
3.13 になる。`build/msvc/openmsx.vcxproj` のビルド前ステップが素の `py` で
`genconfig.py` を呼ぶので、既定が新しい方を向いている必要がある。

**副作用**: 他プロジェクトが `py` / `python` = 3.8 を前提にしていると影響する。
3.8 を明示したい場合は `py -3.8` で呼ぶこと。

Win10 機では `py` の既定が最初から 3.13.14 なので、この地雷は無い（**確認済み**）。

### 2.2 PlatformToolset v143 が入っていないことがある

`build/msvc/openmsx.vcxproj` は `<PlatformToolset>v143</PlatformToolset>`
（VS2022）を指定している。VS2022 が入っていないマシンでは v143 が無い
（Win11 機がこれ。§1.1）。

対処: **msbuild のコマンドラインで `-p:PlatformToolset=v145` を渡して上書きする**。
upstream のファイルを書き換えないので、pull で衝突しない。

この組み合わせ（openMSX × v145）は upstream では試されていない。
Win11 機と Win10 機の両方でビルドが通っている（**確認済み**。§6）。

### 2.3 xiph からのダウンロードが SSL エラーで落ちる

`downloads.xiph.org` はリダイレクトで `ftp.osuosl.org` に飛ぶ。この証明書鎖の
ルートが **emSign Root TLS CA - G1**（eMudhra）で、Windows の証明書ストアに
最初から入っていない。Windows はルート証明書を必要時に取得するが、
**その取得を起こすのは Schannel（CryptoAPI）を使う経路だけ**である。
Python の `ssl` は OpenSSL でストアの中身だけを見るので、取得が起きず
`CERTIFICATE_VERIFY_FAILED` で落ちる（**確認済み**: `openssl s_client` で
鎖のルートを確認し、証明書ストアを検索して不在を確認した）。

**再実行しても直らない**（**確認済み**: Win10 機で 2 回連続で同じ失敗）。
先に Schannel を使う経路で一度アクセスしてルートを取得させると、
以後 Python も通る（**確認済み**: 下記を実行した直後に Python から成功）。

```powershell
# ルート証明書の取得を起こさせるだけ。取得先の URL は build/packages.py にある
Invoke-WebRequest -Uri <失敗した tarball の最終 URL> -Method Head -UseBasicParsing
```

`build/thirdparty_download.py` は tarball ごとに長さと sha256 を検証する
（`verifyPackage`）ので、**別手段で取得して `derived/3rdparty/download/` に
置いても改竄・破損は検出される**。ダウンロード済みのファイルはスキップされる。

### 2.4 vcpkg のグローバル統合が割り込む（**これが最も厄介**）

**Win11 機と Win10 機の両方**に vcpkg がグローバル統合されている
（`%LOCALAPPDATA%/vcpkg/vcpkg.user.props` / `.targets` が
`C:\vcpkg\scripts\buildsystems\msbuild\vcpkg.targets` を読み込む）。
これは**そのマシンの全 MSBuild C++ プロジェクトに無条件で割り込む**。

やっていることは 2 つ（**確認済み**: `vcpkg.targets` の 113-123 行）。

1. `AdditionalIncludeDirectories` に vcpkg の include を足す
2. `AdditionalDependencies` に `lib\*.lib` を足す。
   つまり**インストール済みライブラリを全部リンクする**

openMSX は依存ライブラリを自前で静的にビルドするので、これは両方とも害になる。

- **リンクエラー**: vcpkg の `z.lib`（zlib の import lib）と openMSX の
  `zlib.lib` が衝突し、`LNK2005` が 11 個出て `LNK1169` で落ちる
- **静かな汚染**: libpng が vcpkg の `zlib.h` でコンパイルされ、
  `crc32`/`adler32` を dllimport 扱いする。リンクは `LNK4286` 警告で通ってしまう

**対処: すべての msbuild 呼び出しに `-p:VcpkgEnabled=false` を付ける。**
これで統合ごと無効になる。リポジトリも vcpkg 自体も触らない。

3rdparty を汚染された状態でビルドしてしまった場合は、
`-t:Rebuild` を付けて作り直すこと。`LNK4286` が消えたかで判定できる。

### 2.5 `thirdparty_download.py` は既存のソースを毎回消して展開し直す

`extractPackage()` が `if isdir(packageSrcDir): rmtree(packageSrcDir)` してから
展開する（**確認済み**: `build/thirdparty_download.py:38-55`）。
つまり**用が無いのに走らせると、健全なソースツリーをいったん壊す**。

Win11 機では実際に `rmtree` が `PermissionError [WinError 32]`
（別プロセスが使用中）で中断し、SDL2 のソースが欠けた状態になった。
症状は 3rdparty ビルドでの `C1083`（`dynapi/SDL_dynapi.h` が無い等）。
**もう一度 `thirdparty_download.py` を走らせれば直る。**

要求ライブラリの版が変わったとき以外は走らせないこと。
版は `build/packages.py` で確認できる。

### 2.6 展開時に symlink の警告が出るのは無害

`WARNING: Skipping symlink creation: ... [WinError 1314]` が SDL2 と SDL2_ttf の
展開で出る。Windows で symlink を作るには開発者モードか管理者権限が要るため。
対象は Android プロジェクトと macOS の framework 配下だけで、
**Windows ビルドはこれらを参照しない**（**確認済み**: Win10 機で警告が出た状態から
3rdparty と本体のビルドがどちらもエラー 0 で通った）。

## 3. 手順

初回、およびブランチを切り替えたとき:

```sh
py build/thirdparty_download.py windows
```

ビルド（x64 / Release の例）:

```sh
# MSBuild の場所はマシンごとに違うので決め打ちにしない
MSBUILD=$(vswhere.exe -latest -products "*" -requires Microsoft.Component.MSBuild -find "MSBuild/**/Bin/MSBuild.exe" | head -1)
# vswhere.exe は PATH に無いので、Installer のディレクトリを足しておく:
#   PATH="$PATH:/c/Program Files (x86)/Microsoft Visual Studio/Installer"

OPTS="-nologo -m -p:Configuration=Release -p:Platform=x64 -p:PlatformToolset=v145 -p:VcpkgEnabled=false"
"$MSBUILD" $OPTS build/3rdparty/3rdparty.sln
"$MSBUILD" $OPTS build/msvc/openmsx.sln
```

**`-p:PlatformToolset` は、その MSBuild が属する VS に在るものしか指定できない。**
`vswhere -latest` は最も新しい VS を返すので、複数の VS が入っているマシンでは
返ってきた MSBuild と渡すツールセットが噛み合っているかを確かめること（§1.2）。
噛み合わない組み合わせは**試していない**ので、どう落ちるかは記録がない。

**`PlatformToolset` と `VcpkgEnabled` はマシンの事情である**（§2.2、§2.4）。
vcxproj が指定する v143 が入っていれば `-p:PlatformToolset` は要らないし、
vcpkg のグローバル統合が無ければ `-p:VcpkgEnabled` も要らない。付けたままでも害は無い。

出力先は `derived/x64-VC-Release/install`。

**`msbuild ... | tail` のようにパイプで繋がないこと。** パイプラインの終了コードは
`tail` のものになるので、ビルドが失敗しても後続の `&&` が通ってしまう。
ログはファイルにリダイレクトして、終了コードを直接見る。

Configuration は `Debug` / `Developer` / `Release` の 3 つ。
Developer は assert 有効・最適化なしなので、デバイス実装の反復にはこちらが向く。

## 4. 動かす

ビルドされるのは `openmsx.exe` だけで、`share/` も C-BIOS も
`install` には置かれない。**環境変数で作業ツリーを直接指せば足りる**
（**確認済み**: `FileOperations.cc` の `getSystemDataDir` / `getUserDataDir` は
`OPENMSX_SYSTEM_DATA` / `OPENMSX_USER_DATA` を最優先で読む）。

C-BIOS はリポジトリ内の `Contrib/cbios/` にある（XML と ROM が同じ場所）。
gitignore 済みの `derived/` に置けば作業ツリーを汚さない。

```sh
mkdir -p derived/openmsx-user/machines
cp Contrib/cbios/* derived/openmsx-user/machines/

OPENMSX_SYSTEM_DATA="$(pwd)/share" \
OPENMSX_USER_DATA="$(pwd)/derived/openmsx-user" \
  ./derived/x64-VC-Release/install/openmsx.exe -testconfig -machine C-BIOS_MSX2+
```

`OPENMSX_SYSTEM_DATA` を作業ツリーの `share/` に向けておくと、
`share/extensions/*.xml` の編集がビルドなしで反映される。

**注意**: Windows サブシステムでリンクされているので、`openmsx.exe` は
コンソールに何も出さない。リダイレクトしても空になる。成否は**終了コードで見る**。
`-testconfig` は指定した構成を起動して終了するので、スモークテストに使える。

中身を見たいときは Tcl スクリプトからファイルに書き出す。

```sh
# probe.tcl の例
#   set f [open out.txt w]
#   foreach d [machine_info sounddevice] { puts $f $d }
#   close $f
#   exit
openmsx.exe -machine C-BIOS_MSX2+ -ext HRA_Y8960 -script probe.tcl
```

### 4.1 実機の BIOS ROM

C-BIOS 以外の機種を動かすには BIOS ROM が要る。openMSX は
`<userdata>/systemroms` と `<systemdata>/systemroms` を**再帰的に**走査して
SHA1 で照合する（**確認済み**: `FilePool.cc` の既定値と
`FilePoolCore.cc` の `foreach_file_recursive`）。

**ROM の置き場所はマシンごとに違うので、この文書には書かない。**
`<userdata>/systemroms` の下にディレクトリジャンクションを張って、
各自の ROM 置き場を指すこと。

```sh
# PowerShell。<ROM置き場> は各自の環境に読み替える
New-Item -ItemType Junction `
  -Path "derived\openmsx-user\systemroms\local" -Target "<ROM置き場>"
```

`derived/` は gitignore 済みなので、リンクを張っても追跡対象にならない。
ROM 置き場が複数あるなら、名前を変えてジャンクションを並べればよい。
openMSX は SHA1 で照合するので、重複して見えても害はない
（**確認済み**: Win10 機で 2 本張り、片方にしか無い ROM を要求する機種が起動した）。

**リンク先は BIOS だけを含む部分木に絞る。** ゲーム ROM を含む木を指すと、
用の無いファイルまで SHA1 走査の対象になる。ゲームは明示のパスで読ませるもので、
`systemroms` の用途ではない。

ジャンクションを消すときは、**リンクだけが消えてリンク先が残ることを確かめてから**
消すこと。`Remove-Item -Recurse` がリンクを辿ってリンク先を消す事故は、古い
PowerShell の既知の不具合として語られている。
PowerShell 5.1.19041.6456 では**辿らない**（**確認済み**: 使い捨てディレクトリに
ジャンクションを張り、目印のファイルを置いて `Remove-Item -Recurse -Force` を
掛けたところ、リンクだけが消えて目印は残った）。版が違えば結果も違いうるので、
確信が無いなら `[System.IO.Directory]::Delete()` か `cmd /c rmdir` を使う。
どちらもリンクしか消さない。

## 5. 別のマシンで再開するとき

本書の §1 と §2 は**実際に踏んだ地雷の記録**であって、
どのマシンでも同じとは限らない。別のマシンでは次を確かめ直すこと。

1. **Python が 3.9 以上か**（§2.1）。`py -0p` で見る
2. **使える PlatformToolset と、それがどの VS に属するか**（§2.2、§1.2）。
   VS ごとに `MSBuild/Microsoft/VC/*/Platforms/x64/PlatformToolsets` を列挙する
3. **vcpkg のグローバル統合の有無**（§2.4）。
   `%LOCALAPPDATA%/vcpkg/vcpkg.user.props` があるかどうか
4. **xiph のルート証明書がストアに在るか**（§2.3）。
   無ければ Schannel 経由で一度取得させてからダウンロードする
5. **ROM の置き場所**（§4.1）。マシンごとに違うのでこの文書には書いていない

`derived/` は全部生成物なので、リポジトリを clone して §3 の手順を踏めば復元できる。
C-BIOS はリポジトリ内の `Contrib/cbios/` にあるので追加の入手は要らない。

## 6. 実行経緯

### 2026-09-08

- 環境を調査。VS2026 Community と VS2019 Professional、Python 3.8.2 を確認
- Python 3.8.2 で `thirdparty_download.py` が落ちることを確認 → 3.13.15 を追加
- PlatformToolset v143 が無いことを確認 → v145 で上書きする方針を決定
- 3rdparty のソース取得を実施
- **`master` で v145 ビルドが通ることを確認（確認済み）**
  - 3rdparty: 0 エラー / 247 警告 / 58 秒
  - openMSX 本体: 0 エラー / 76 警告 / 6 分 57 秒
  - `openmsx.exe --version` が終了コード 0
  - `-testconfig -machine C-BIOS_MSX2+` が終了コード 0。
    実際に MSX2+ の構成を起動できている
  - **v145 固有のエラーは 1 件も出なかった。** 警告はすべて C4267/C4701 系で、
    upstream が v143 でも出しているものと同種
- `buppu3` remote を追加し、`y8960` ブランチから同名のローカルブランチを作成
- `y8960` ブランチのビルドで **vcpkg のグローバル統合による衝突**が発覚（§2.4）。
  `master` では偶然通っていたが、`LNK4286` が出ていたので**汚染はしていた**。
  `-p:VcpkgEnabled=false` を全ビルドに付ける方針にし、3rdparty を作り直して
  `LNK4286` が消えることを確認した
- **`y8960` ブランチのビルドが通ることを確認（確認済み）**
  - 3rdparty: 0 エラー / 247 警告 / 52 秒
  - openMSX 本体: 0 エラー / 11 警告 / 2 分 16 秒
  - `-testconfig -machine C-BIOS_MSX2+ -ext HRA_Y8960` が終了コード 0
  - Tcl で `machine_info` を吐かせ、Y8960 の全デバイス
    （SSG×2 / DCSG×2 / OPLL×2 / SCC / MSX-TIMER / MIXER）が
    実際に登録されていることを確認
  - `Y8960 SCC` の ROM は SHA1 `da39a3ee…`（空ファイル）。ROM 無しで動く
- 実機 ROM を `systemroms` 配下のジャンクションで参照する形にした（§4.1）。
  `Sony_HB-F1XV` / `Panasonic_FS-A1GT` / `Panasonic_FS-A1FX` は終了コード 0。
  `Panasonic_FS-A1WSX` は 1 で失敗した。**原因は未特定**
  （必要な ROM が揃っていない可能性が高いが、確かめていない）
- `y8960` ブランチを最新 master の上に載せ替えた後、`thirdparty_download.py` を
  不要に走らせて SDL2 のソースを壊した。再実行で復旧（§2.5）

### 2026-09-09（Win10 機の立ち上げ）

- §5 の 4 点を確認。Python 3.13.14（地雷なし）、v143 と v145 の両方が使える、
  vcpkg のグローバル統合あり、ROM 置き場は既存のものを流用
- **§2.3 の「一過性」という判断が誤りだったことが判明。**
  再実行では直らず、原因は emSign のルート証明書がストアに無いことだった。
  Schannel 経由で一度取得させると通る。§2.3 を書き直した
- ツールセットは **v145 を選んだ**（理由と前提は §1.2）。v143 は試していない
- **3rdparty のビルドが通ることを確認（確認済み）**
  - 0 エラー / 247 警告。Win11 機と警告数が一致
- **openMSX 本体のビルドが通ることを確認（確認済み）**
  - 0 エラー / 88 警告 / **28 分 33 秒**。
    Win11 機の 2 分 16 秒〜6 分 57 秒に対して 4〜12 倍かかる。
    バックグラウンド実行の待ち時間を見積もるときはこちらを基準にする
  - `LNK4286` は 0 件。vcpkg による汚染は起きていない（§2.4）
- **スモークテスト（確認済み、すべて終了コード 0）**
  - `--version`
  - `-testconfig -machine C-BIOS_MSX2+`
  - `-testconfig -machine C-BIOS_MSX2+ -ext HRA_Y8960`
  - 実機 8 機種。**Win11 機で失敗していた `Panasonic_FS-A1WSX` も通った**
    （2026-09-08 で原因未特定としていた件）。
    **推測**: Win11 機の失敗は ROM 不足。根拠は、コミットもビルド構成も機種 XML も
    同じで、変わったのは参照している ROM の集合だけであること。
    Win11 機の ROM 置き場は観測していないので、そちらの不在は確かめていない
- **Y8960 の全デバイスが登録されていることを確認（確認済み）**。
  Tcl で `machine_info device` を吐かせ、`MSX-TIMER` / `Y8960-SSGS` /
  `SNPSG` ×2 / `Y8960-OPLL` ×2 / `Y8960-OPL2` ×2 / SCC / `Y8960-MIXER` を確認。
  SSGS は 1 デバイスで、内部に SSG が 2 系統
  （`Y8960SSGS.hh` の `std::array<Y8960SsgCore, NUM_UNITS>`）
- **ウィンドウが出ないことを実測（確認済み）**。
  `-script` 実行中に `MainWindowHandle` を 0.5 秒間隔で 8 回とり、すべて 0
- ジャンクションの削除で `Remove-Item -Recurse` がリンク先を消すかを実測。
  PowerShell 5.1.19041.6456 では**消さない**。§4.1 に記録
