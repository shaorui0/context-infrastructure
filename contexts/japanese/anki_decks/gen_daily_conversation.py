#!/usr/bin/env python3
"""生成「日语日常口语」Anki 闪卡 CSV。
语料：tmp.txt 的日常/篮球实用句 + 口语连接词/相槌。
列：front\tback\ttags\tfront_reading\tmeaning  (tab 分隔)
"""
import csv
from pathlib import Path

OUT_DIR = Path(__file__).parent / "out"


def back_html(reading, meaning, structure, expand=None):
    parts = [
        f'<div class="back-reading">{reading}</div>',
        f'<div class="back-meaning">{meaning}</div>',
        f'<div class="back-structure">{structure}</div>',
    ]
    if expand:
        parts.append(f'<div class="back-expand">{expand}</div>')
    return "\n".join(parts)


# (front, reading_kana, meaning, structure_html, expand_html_or_None, tags)
CARDS = [
    # ── 日常 / 篮球实用句 (来源 tmp.txt) ──────────────────────────────
    ("フリーだよ、パス！", "フリーだよ、パス",
     "你没人防，传球！",
     "フリー = 无人防守(free) ＋ だよ = 强调 ＋ パス = 传球(pass)",
     "球场上喊话用，casual", "japanese daily_phrases basketball casual"),

    ("上手ですね！", "じょうずですね",
     "你很厉害啊！",
     "上手(じょうず) = 擅长 ＋ です = 礼貌 ＋ ね = 寻求认同<br><b>句型：</b>[名词]が上手です",
     "夸人最常用；反义：下手(へた)", "japanese daily_phrases praise polite"),

    ("プレーがうまいですね。", "プレーがうまいですね",
     "你打得真好。",
     "プレー = 打法/表现(play) ＋ が ＋ うまい = 厉害 ＋ ですね",
     "うまい 比 上手 更口语、更随意", "japanese daily_phrases praise"),

    ("バスケ上手ですね。", "バスケじょうずですね",
     "你篮球打得真好。",
     "バスケ = 篮球(バスケットボール简称) ＋ 上手 ＋ ですね",
     None, "japanese daily_phrases basketball praise polite"),

    ("めっちゃ上手ですね！", "めっちゃじょうずですね",
     "你超厉害的！",
     "めっちゃ = 超级(关西腔，≈とても) ＋ 上手 ＋ ですね",
     "年轻人高频；更口语：めっちゃうまい", "japanese daily_phrases praise casual"),

    ("週に何回くらいバスケをするんですか？", "しゅうになんかいくらいバスケをするんですか",
     "你一周大概打几次篮球？",
     "週に = 每周 ＋ 何回(なんかい) = 几次 ＋ くらい = 大约 ＋ するんですか = 询问(んです 表关心)",
     "搭讪/拉近关系常用问句", "japanese daily_phrases basketball question polite"),

    ("普段いつ来てるんですか？", "ふだんいつきてるんですか",
     "你平时什么时候来？",
     "普段(ふだん) = 平时 ＋ いつ = 何时 ＋ 来てる = 来(来ている 缩约) ＋ んですか",
     "约下次见面的铺垫句", "japanese daily_phrases question"),

    ("また今度一緒にやりましょう！", "またこんどいっしょにやりましょう",
     "下次再一起玩吧！",
     "また = 再 ＋ 今度(こんど) = 下次 ＋ 一緒に = 一起 ＋ やりましょう = 做吧(ましょう 邀约)",
     "告别时留后路的万能句", "japanese daily_phrases invite polite"),

    ("同じチームでやりましょう。", "おなじチームでやりましょう",
     "我们一队吧。",
     "同じ(おなじ) = 相同 ＋ チーム ＋ で = 以…(方式) ＋ やりましょう",
     None, "japanese daily_phrases basketball invite"),

    ("一緒にチーム組んで試合しませんか？", "いっしょにチームくんでしあいしませんか",
     "要不要一起组队比赛？",
     "チームを組む = 组队 ＋ て形连接 ＋ 試合(しあい) = 比赛 ＋ しませんか = 要不要…(委婉邀约)",
     "〜ませんか 比 〜ましょう 更礼貌、给对方拒绝空间", "japanese daily_phrases basketball invite polite"),

    ("1対1で勝負しましょう！", "いったいいちでしょうぶしましょう",
     "来单挑吧！",
     "1対1(いったいいち) = 一对一 ＋ で ＋ 勝負(しょうぶ) = 决胜负 ＋ しましょう",
     None, "japanese daily_phrases basketball invite"),

    ("あなたは相手チームです。", "あなたはあいてチームです",
     "你是对方队的。",
     "あなた = 你 ＋ は ＋ 相手(あいて) = 对手 ＋ チーム ＋ です",
     "分队时用；相手 = 对手/对方", "japanese daily_phrases basketball"),

    ("ずっと負けてたけど、やっと勝てた！", "ずっとまけてたけど、やっとかてた",
     "一直输，终于赢了！",
     "ずっと = 一直 ＋ 負けてた = 一直输(負けていた 缩约) ＋ けど = 但 ＋ やっと = 终于 ＋ 勝てた = 赢了(勝てる 可能形过去)",
     "勝つ→勝てた(能赢/赢到了)；情绪句", "japanese daily_phrases casual"),

    ("日本での生活には慣れましたか？", "にほんでのせいかつにはなれましたか",
     "习惯日本的生活了吗？",
     "日本での生活 = 在日本的生活 ＋ に ＋ 慣れる(なれる) = 习惯 ＋ ましたか",
     "关心对方的高频寒暄", "japanese daily_phrases question polite"),

    ("もう少し丁寧にお願いします。", "もうすこしていねいにおねがいします",
     "麻烦说(做)得再仔细/客气一点。",
     "もう少し = 再…一点 ＋ 丁寧に(ていねいに) = 仔细地/礼貌地 ＋ お願いします = 拜托",
     "听不清或想让对方放慢时用", "japanese daily_phrases request polite"),

    ("リバウンドを取ったら、そのまま攻撃を続けます。", "リバウンドをとったら、そのままこうげきをつづけます",
     "抢到篮板后，就直接继续进攻。",
     "リバウンドを取る = 抢篮板 ＋ たら = …之后/的话 ＋ そのまま = 就那样 ＋ 攻撃(こうげき)を続ける = 继续进攻",
     None, "japanese daily_phrases basketball"),

    ("どちらが先にボールを持ちますか？", "どちらがさきにボールをもちますか",
     "哪边先持球？",
     "どちら = 哪边 ＋ が ＋ 先に(さきに) = 先 ＋ ボールを持つ = 持球 ＋ ますか",
     None, "japanese daily_phrases basketball question polite"),

    ("唐揚げを一つお願いします。", "からあげをひとつおねがいします",
     "来一份炸鸡。",
     "唐揚げ(からあげ) = 日式炸鸡 ＋ を ＋ 一つ(ひとつ) = 一份 ＋ お願いします = 点餐万能句",
     "点单：[东西]を[数量]お願いします", "japanese daily_phrases order polite"),

    ("今どんな気持ち？", "いまどんなきもち",
     "现在什么感觉？",
     "今 = 现在 ＋ どんな = 怎样的 ＋ 気持ち(きもち) = 心情/感觉 (省略です = 口语)",
     "调侃/起哄常用", "japanese daily_phrases casual"),

    ("気持ちいい！", "きもちいい",
     "好舒服！／好爽！",
     "気持ち = 感觉 ＋ いい = 好 → 固定形容词「気持ちいい」",
     "反义：気持ち悪い(きもちわるい) = 恶心/难受", "japanese daily_phrases casual"),

    # ── 口语连接词 / 相槌 ────────────────────────────────────────────
    ("あの…／えーと…", "あの、えーと",
     "嗯…／那个…（开口或思考时的停顿）",
     "あの = 引起注意、开口时的「那个…」 ＋ えーと = 思考措辞时的「嗯…让我想想」",
     "争取思考时间、避免冷场；最基础的填充词", "japanese connectors filler"),

    ("ということ", "ということ",
     "也就是说…／就是这么回事",
     "…という = 所谓/叫做 ＋ こと = 事情 → 「ということ」归纳总结前面的话",
     "つまり〜ということ = 也就是说〜；〜ということですね = 你意思是〜对吧(确认)", "japanese connectors"),

    ("どういう意味？", "どういういみ",
     "什么意思？",
     "どういう = 怎样的 ＋ 意味(いみ) = 意思 → 没听懂时反问",
     "礼貌版：どういう意味ですか？", "japanese connectors question"),

    ("まさか！", "まさか",
     "不会吧！／怎么可能",
     "まさか = 表示难以置信、出乎意料(动漫高频)",
     "まさか〜とは思わなかった = 没想到竟然〜", "japanese connectors reaction"),

    ("それで…／で、", "それで、で",
     "然后…／那(结果)呢？",
     "それで = 接续前文「于是/然后」；口语常缩成「で、」开头",
     "で、どうなった？= 然后呢，后来怎样了？", "japanese connectors conjunction"),

    ("だから", "だから",
     "所以",
     "だ ＋ から = 表示结论/原因「所以」",
     "だからね = 所以说嘛(带情绪)；语气重时显说教，注意场合", "japanese connectors conjunction"),

    ("それに", "それに",
     "而且、再加上",
     "それ ＋ に → 追加信息「而且」",
     "安いし、それに美味しい = 又便宜，而且好吃", "japanese connectors conjunction"),

    ("じゃあ", "じゃあ",
     "那么、那(就)",
     "では 的口语缩约 → 转换话题或下结论「那就…」",
     "じゃあ、また！= 那回头见！", "japanese connectors conjunction"),

    ("なるほど", "なるほど",
     "原来如此",
     "相槌(あいづち)，表示理解、认同对方",
     "なるほどね = 原来如此啊(更随意)", "japanese connectors aizuchi"),

    ("やっぱり", "やっぱり",
     "果然／还是…",
     "やはり 的口语形 → 「果然如我所料」或「还是…(改主意)」",
     "やっぱりやめる = 我还是不做了；やっぱりね = 果然吧", "japanese connectors"),
]


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "daily_conversation.csv"
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["front", "back", "tags", "front_reading", "meaning"])
        for front, reading, meaning, structure, expand, tags in CARDS:
            back = back_html(reading, meaning, structure, expand)
            w.writerow([front, back, tags, reading, meaning])
    print(f"{out}")
    print(f"notes={len(CARDS)} cards={len(CARDS)*2}")


if __name__ == "__main__":
    main()
