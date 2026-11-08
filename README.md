# recipes

家庭料理のレシピを Markdown で残しているリポジトリです。同じ内容を静的サイトとして GitHub Pages で公開しています。

**公開サイト: https://tsubotan1985.github.io/recipes/**

## レシピ一覧

- [さわやか風「げんこつハンバーグ」（黄金比ブレンド・卵不使用・オーブン併用）](genkotsu-hamburg.md)
- [甘辛コクの 回鍋肉（日本式）](hoikoro-japanese-style.md)
- [マルちゃん「北の味わい ガラ炊き味噌ラーメン」で作る 火山らあめん風](kazan-ramen.md)
- [ミラノ風リゾット（Risotto alla Milanese）](risotto-alla-milanese.md)
- [帯広×菱田屋インスパイア「焦がしニンニク生姜焼き」 (豚バラver.)](shogayaki.md)
- [茨城ご当地「スタミナラーメン」再現レシピ](stamina-ramen.md)
- [圧倒的香ばしさの 鶏肉とカシューナッツ炒め（腰果鶏丁）](toriniku-cashew-itame.md)

## 使い方

各レシピは 1 ファイル 1 品の Markdown です。材料と手順がそのまま読めます。

## サイトの作り方

`docs/` は `tools/build_site.py` が生成した静的ファイルです（依存パッケージなし、Python 3 のみ）。

```bash
python3 tools/build_site.py          # docs/ を再生成
python3 tools/build_site.py --serve  # 生成して http://localhost:8099 で確認
```

GitHub Pages の公開元は `main` ブランチの `/docs` です。レシピを追加・修正したら、上のコマンドで `docs/` を作り直してコミットしてください。

### レシピを追加するとき

1. `レシピ名.md` を作り、先頭にメタ情報を HTML コメントで書く（GitHub の表示には出ません）。

   ```markdown
   <!--
   category: 中華
   servings: 2人分
   tags: 中華, 炒め物, ナッツ
   summary: 一覧カードに出す 1 文の説明。
   -->
   # 料理名

   導入の文章。

   ---

   ## 材料 (2人分)

   ### グループ名
   * **材料名**: 分量 （補足）

   ---

   ## 手順

   ### 1. 下ごしらえ
   手順の本文。

   ## ポイント
   * **要点:** 説明
   ```

2. `python3 tools/build_site.py` を実行して `docs/` を更新する。
3. `docs/` と `*.md` をまとめてコミットする。

見出しは `## 材料` / `## 手順`（または `## 作り方`・`## 調理手順`）、`## 特徴`、`## ポイント`、`## おすすめの食べ方`、`## 備考` を認識します。材料は `* **名前**: 分量 （補足）` の形にすると、サイト上でチェックボックス付きの材料リストになります。
