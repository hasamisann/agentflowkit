# workflow-templates

OpenCode、Claude Code、Codex で使う spec-driven 開発テンプレートです。

## ワークフロー

```text
INIT -> SPECIFY-DESIGN -> PLAN-TASKS -> IMPLEMENT

INVESTIGATE -> FIX-TASKS -> IMPLEMENT
```

## 役割分担

- `AGENTS.md`: 共有の正本ルール
- `CLAUDE.md`: `@AGENTS.md` を読み込む Claude Code 用ラッパー
- `.workflow/procedures/`: 各フェーズの実行手順
- `.workflow/scripts/review_driver.py`: Codex review loop の実行ヘルパー
- `.workflow/config/codex-model.txt`: workflow 全体で使う Codex モデルの単一設定
- `.claude/skills/`: Claude Code の明示起動 skill
- `.agents/skills/`: Codex の repo 共有 skill
- `.opencode/commands/`: OpenCode の明示起動 command

## 成果物

- `.spec/cycles/manifest.md`: 全 cycle の台帳
- `.spec/cycle_index.md`: 現在アクティブな cycle のポインタ
- `.spec/cycles/<cycle>/CYCLE.md`: 要件と設計をまとめた cycle 文書
- `.spec/cycles/<cycle>/tasks/*.md`: 実装タスク
- `.spec/cycles/<cycle>/tasks/dependencies.md`: wave と依存関係、進捗状態
- `.spec/bugs/<bug-id>/INVESTIGATION.md`: バグ調査文書
- `.spec/bugs/<bug-id>/tasks/*.md`: バグ修正タスク
- `.spec/bugs/<bug-id>/tasks/dependencies.md`: バグ修正用 wave と依存関係、進捗状態
- `.workflow/project_context.md`: プロジェクト固有の build/test/構成情報

これらの workflow 用ファイルはローカル専用です。対象プロジェクトでは `.git/info/exclude` に登録し、通常の実装履歴と分けて扱います。

## 必須レビュー

文書 1 件または実装タスク 1 件ごとに、必ず次を完了します。

1. 作成または実装する
2. review state を初期化する
3. `codex exec` の read-only review round を行う
4. `CRITICAL` / `MAJOR` を必須対応し、`MIDDLE` / `MINOR` は任意対応する
5. blocking finding がなくなるまで、または上限ターンに達するまで繰り返す

共通条件:

- review 設定は `.workflow/config/codex-review.toml` で一元管理する
- `parallel_reviews = 3`
- `max_review_turns = 10`
- `blocking_severities = ["critical", "major"]`
- schema は `.workflow/review/codex-review-schema.json`
- review log は `logs/reviews/` 配下
- 1 コマンド実行につき 1 canonical review log を使い、同じコマンド中の反復レビューではそのファイルを上書きする
- reviewer 別 raw log は補助診断用として同じディレクトリに一時出力してよい
- 実装レビューでは task file 全文も prompt に含める
- 1 review round は共通参照を含む reviewer 別 prompt の `codex exec` を並列に 3 本走らせ、その結果を統合して扱う
- reviewer ごとに `reasoning_effort` と document / implementation 用 lens を変えられるが、docs-first review と source-of-truth ルールは全 reviewer で共通
- 各 reviewer はまず docs-first review を行い、その後で通常 review を行う
- 提供された docs は review の source of truth とし、それと矛盾する finding や修正提案は出してはならない
- `plan-tasks` の review では active cycle の `CYCLE.md` を必須参照として prompt に含める
- `implement` の review では対応 task file を task-specific requirements の source of truth として扱う
- `implement` では `codex exec` review が task file と衝突した場合、常に task file を正とする
- `approved: true` と空の `findings` は「blocking finding なし」を意味し、`advisory_findings` は残ってよい

通常は `.workflow/scripts/review_driver.py` を使います。詳細は `.workflow/procedures/review-loop.md` を参照してください。

## セットアップ

### PowerShell

```powershell
.\init-agents.ps1 -TargetDir C:\path\to\MyProject -InitGit
```

GitHub リポジトリも作る場合:

```powershell
.\init-agents.ps1 -TargetDir C:\path\to\MyProject -GitHubRepo owner/my-project
```

### POSIX shell

```bash
./init-agents.sh --target-dir /path/to/MyProject --init-git
```

GitHub リポジトリも作る場合:

```bash
./init-agents.sh --target-dir /path/to/MyProject --github-repo owner/my-project
```

初期化スクリプトは次を行います。

- workflow 関連ファイルを対象プロジェクトへコピーする
- 既存 `.gitignore` を上書きせずに必要エントリだけ追加する
- Git リポジトリがある場合は `.git/info/exclude` にローカル専用ファイルを追加する
- 新規に Git を初期化した場合だけ、必要最小限の tracked ファイルを初回コミットする
- `-GitHubRepo` / `--github-repo` 指定時は remote 作成と `origin` 設定を試みるが、既存の別 `origin` は上書きしない

## 配置されるファイル

```text
MyProject/
├── AGENTS.md
├── CLAUDE.md
├── .workflow/
│   ├── procedures/
│   ├── review/
│   ├── scripts/
│   ├── templates/
│   └── project_context.md
├── .opencode/
│   └── commands/
├── .claude/
│   └── skills/
├── .agents/
│   └── skills/
└── .spec/
    ├── cycle_index.md
    ├── cycles/
    │   └── manifest.md
    └── bugs/
```

Codex 実行時には `.workflow/scripts/codex.ps1`、`.workflow/scripts/codex.cmd`、`.workflow/scripts/codex.sh` が `.workflow/config/codex-model.txt` のモデル指定を自動で付与します。

## 実行方法

### OpenCode

OpenCode は `/` command を使います。

```text
/specify-design
/plan-tasks
/implement wave 1
```

### Claude Code

Claude Code は `.claude/skills/` にある skill を `/` で呼びます。各 workflow skill は `disable-model-invocation: true` なので自動発火せず、明示起動専用です。

```text
/specify-design new export pipeline
/plan-tasks
/implement .spec/cycles/c01-example/tasks/impl-001-example.md
```

`specify-design`, `plan-tasks`, `investigate`, `fix-tasks` の Claude skill には Stop hook が付き、skill の終了時に review helper を自動実行します。

### Codex

Codex では repo 共有 skill を使います。custom prompts は deprecated なので、このテンプレートでは `.agents/skills/` を正規経路にします。

Codex の使用モデルは `.workflow/config/codex-model.txt` で固定します。最新モデルへ切り替えたいときはこの 1 ファイルだけを書き換えてください。

まず必要なら wrapper から起動します。

```powershell
.\.workflow\scripts\codex.ps1
```

または:

```text
.workflow\scripts\codex.cmd
./.workflow/scripts/codex.sh
```

その後、`/skills` または `$` で skill を明示起動します。

```text
$specify-design start a new reporting workflow
$plan-tasks for the active cycle
$implement the task file .spec/cycles/c01-example/tasks/impl-001-example.md
```

Codex skills は repo 共有の playbook として使い、具体的な対象は現在のユーザー要求で与えます。

## review helper の使い方

文書フェーズ開始時:

```bash
python "$(git rev-parse --show-toplevel)/.workflow/scripts/review_driver.py" prepare --tool opencode --phase plan-tasks --arguments "$ARGUMENTS"
```

新しいユーザー入力、手動レビュー結果、または明示的な review round reset 指示を受けたら、次の workflow review 前に同じ `prepare` を再実行して round をリセットします。

文書フェーズ終了時:

```bash
python "$(git rev-parse --show-toplevel)/.workflow/scripts/review_driver.py" finish --tool opencode --phase plan-tasks
```

実装フェーズ開始時:

```bash
python "$(git rev-parse --show-toplevel)/.workflow/scripts/review_driver.py" prepare --tool opencode --phase implement --arguments "$ARGUMENTS"
```

実装タスクごとの review:

```bash
python "$(git rev-parse --show-toplevel)/.workflow/scripts/review_driver.py" review-task --tool opencode --task-file ".spec/cycles/c01-example/tasks/impl-001-example.md"
```

同じ考え方で `--tool` を `claude` や `codex` に置き換えて使います。

## バグフロー

```text
.spec/bugs/
└── b001-null-crash/
    ├── INVESTIGATION.md
    └── tasks/
        ├── dependencies.md
        ├── fix-001-add-regression-test.md
        └── fix-002-fix-null-guard.md
```

推奨順:

1. `/investigate` または対応 skill で再現、失敗ログ、根本原因、影響範囲、回帰戦略、対象 branch を確定する
2. `/fix-tasks` または対応 skill で regression test -> root-cause fix -> hardening の順に分解する
3. `/implement bug <bug-id> wave <N>` または対応 skill で 1 タスクずつ TDD と Codex review loop を完了する
