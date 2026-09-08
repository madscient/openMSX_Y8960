# このマシンでのビルド環境

対象マシン: Windows 11 Pro 26200 / x64
最終更新: 2026-09-08

upstream の一般的な手順は `doc/manual/compile.html` の 5章
"Stand-alone Binary" にある。本書はそこに書かれていない、
**このマシン固有の事情と、そこで詰まった点の記録**である。

## 1. 環境（2026-09-08 時点、すべて確認済み）

| 項目 | 値 | 確認方法 |
|---|---|---|
| Visual Studio | Community 2026 (18.x) / `C:\Program Files\Microsoft Visual Studio\18\Community` | `vswhere -all -property installationPath` |
| （同上） | Professional 2019 も入っているが **openMSX には使えない**（v142 は C++23 非対応） | 同上 |
| MSBuild | 18.9.1.35102 / `...\18\Community\MSBuild\Current\Bin\MSBuild.exe` | `MSBuild.exe -version` |
| 利用可能な PlatformToolset (x64) | **v145 と ClangCL のみ** | `MSBuild\Microsoft\VC\v180\Platforms\x64\PlatformToolsets` を列挙 |
| MSVC ツールチェイン | 14.44.35207 / 14.51.36231 / 14.52.36615 | `VC\Tools\MSVC` を列挙 |
| Python | 3.13.15 (`py` の既定) と 3.8.2 が併存 | `py -0p` |

## 2. このマシン固有の詰まりどころ

### 2.1 Python 3.8 では 3rdparty のダウンロードが落ちる

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

### 2.2 PlatformToolset v143 が入っていない

`build/msvc/openmsx.vcxproj` は `<PlatformToolset>v143</PlatformToolset>`
（VS2022）を指定しているが、このマシンには v145 しか無い（§1）。

対処: **msbuild のコマンドラインで `-p:PlatformToolset=v145` を渡して上書きする**。
upstream のファイルを書き換えないので、pull で衝突しない。

この組み合わせ（openMSX × v145）は upstream では試されていない。

### 2.3 ダウンロードが SSL エラーで落ちることがある

`downloads.xiph.org` からのリダイレクト先 (`ftp.osuosl.org`) で
`CERTIFICATE_VERIFY_FAILED` が出ることがある。同じ URL を直後に叩くと
成功したので**一過性**（Windows がルート証明書を遅延取得するため）と判断した。
再実行すればよい。ダウンロード済みのファイルはスキップされる。

### 2.4 vcpkg のグローバル統合が割り込む（**これが最も厄介**）

このマシンには vcpkg がグローバル統合されている
（`%LOCALAPPDATA%/vcpkg/vcpkg.user.props` / `.targets` が
`C:\vcpkg\scripts\buildsystems\msbuild\vcpkg.targets` を読み込む）。
これは**このマシンの全 MSBuild C++ プロジェクトに無条件で割り込む**。

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

このマシンでは実際に `rmtree` が `PermissionError [WinError 32]`
（別プロセスが使用中）で中断し、SDL2 のソースが欠けた状態になった。
症状は 3rdparty ビルドでの `C1083`（`dynapi/SDL_dynapi.h` が無い等）。
**もう一度 `thirdparty_download.py` を走らせれば直る。**

要求ライブラリの版が変わったとき以外は走らせないこと。
版は `build/packages.py` で確認できる。

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

**`PlatformToolset` と `VcpkgEnabled` もこのマシンの事情である**（§2.2、§2.4）。
別のマシンでは要否が変わる。vcxproj が指定する v143 が入っていれば
`-p:PlatformToolset` は要らないし、vcpkg のグローバル統合が無ければ
`-p:VcpkgEnabled` も要らない。付けたままでも害は無い。

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

## 5. 別のマシンで再開するとき

本書の §1 と §2 は**このマシンで実際に踏んだ地雷の記録**であって、
どのマシンでも同じとは限らない。別のマシンでは次を確かめ直すこと。

1. **Python が 3.9 以上か**（§2.1）。`py -0p` で見る
2. **使える PlatformToolset**（§2.2）。
   `MSBuild/Microsoft/VC/*/Platforms/x64/PlatformToolsets` を列挙する
3. **vcpkg のグローバル統合の有無**（§2.4）。
   `%LOCALAPPDATA%/vcpkg/vcpkg.user.props` があるかどうか
4. **ROM の置き場所**（§4.1）。マシンごとに違うのでこの文書には書いていない

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
