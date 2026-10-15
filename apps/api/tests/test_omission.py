import asyncio

from app import omission as om

SRC = ("夜明け前の集落に、乾いた風が吹いていた。\n「起きろ、ガルド。恐竜が柵を越えた」\n"
       "リナの声に、ガルドは毛皮の寝床から跳ね起きた。槍を掴み、焚き火の残り火を蹴り散らして外へ出る。")


def test_split_sentences_keeps_quotes_and_handles_french_and_decimals():
    assert om.split_sentences("「起きろ、ガルド。恐竜が柵を越えた」") == ["「起きろ、ガルド。", "恐竜が柵を越えた」"]
    assert om.split_sentences("« Lève-toi. » Il partit.") == ["« Lève-toi. »", "Il partit."]
    assert om.split_sentences("It costs 3.5 yen. Really?!\nNext line") == ["It costs 3.5 yen.", "Really?!", "Next line"]
    assert om.split_sentences("") == []


def test_omitted_sentences_uses_the_floor_and_ignores_tiny_sentences():
    src = ["夜明け前の集落に、乾いた風が吹いていた。", "恐竜が柵を越えた」", "はい。"]
    sv = [[1.0, 0.0], [0.0, 1.0], [0.0, 1.0]]
    out = [[1.0, 0.0], [0.2, 0.1]]
    got = om.omitted_sentences(src, sv, out, [])
    assert got == ["恐竜が柵を越えた」"]  # "はい。" is too short to judge
    assert om.omitted_sentences(src, sv, out + [[0.0, 1.0]], []) == []


def test_find_omissions_end_to_end_with_a_fake_embedder():
    covered = "The village before dawn was swept by a dry wind.\n“Wake up, Gard.”\nAt Lina's voice, Gard sprang up. He grabbed his spear and went outside."
    vocab = {"風": 0, "起きろ": 1, "恐竜": 2, "リナ": 3, "槍": 4}
    en = {"wind": 0, "Wake": 1, "dinosaur": 2, "Lina": 3, "spear": 4}

    async def embed(texts):
        out = []
        for t in texts:
            v = [0.0] * 5
            for k, i in {**vocab, **en}.items():
                if k in t:
                    v[i] = 1.0
            out.append(v if any(v) else [0.01] * 5)
        return out
    missing = asyncio.run(om.find_omissions(SRC, covered, embed))
    assert missing == ["恐竜が柵を越えた」"]
    full = covered.replace("“Wake up, Gard.”", "“Wake up, Gard. A dinosaur has crossed the fence.”")
    assert asyncio.run(om.find_omissions(SRC, full, embed)) == []

    async def broken(texts):
        raise RuntimeError("model not pulled")
    assert asyncio.run(om.find_omissions(SRC, covered, broken)) == []  # a broken checker never blocks
    assert asyncio.run(om.find_omissions("短い。", "Short.", embed)) == []  # too little text
