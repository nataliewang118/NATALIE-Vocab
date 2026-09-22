# 句子练习的数据管线。三个子命令：
#   python _build_sents.py pick      从 Tatoeba 英文语料里给每个词挑一句，写进 原始数据/sentences.txt
#   python _build_sents.py zh-merge  把 _tr/out_*.tsv 的翻译并回 sentences.txt 的第三列
#   python _build_sents.py inject    把 sentences.txt 灌进 index.html 的 SENTS / TRANS 常量（挖空后）
#
# sentences.txt 是**可编辑的中间产物**：一行一句 `word | 英文句子 | 整句中文(可空，写 - 表示不给)`。
# pick 只是给个初稿，觉得哪句不合适直接改那一行再 inject 就行，别改 index.html 里的 SENTS。
import bz2, io, re, sys, json, pathlib, collections

sys.stdout.reconfigure(encoding='utf-8')
BASE = pathlib.Path(__file__).parent
SRC  = BASE / '原始数据'
DATA = BASE / '_data'
TXT  = SRC / 'sentences.txt'

def load_words():
    m = re.search(r'var WORDS = (\[.*?\]);', (BASE/'index.html').read_text(encoding='utf-8'), re.S)
    if not m:
        sys.exit('index.html 里没找到 WORDS，先跑 _build_words.py')
    return json.loads(m.group(1))

TOK = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")

# 句子里出现这些说明是句子本身有毛病，或者当例句太别扭，直接不要
BADCH = re.compile(r'[\[\]{}<>|~^*_\\@#]|https?://|www\.|\d')

# 语料是众包的，什么话都有。背单词的例句不该出现这些：性、脏话、血腥、毒品、醉酒。
# 只拦明显不合适的那批；war/death/religion 这类留在里面——它们本身就是正常的词义场景
BADWORD = re.compile(
    r'\b(?:sex|sexual|sexy|porn\w*|naked|nude|rape|whore|prostitut\w*|pregnan\w*|'
    r'fuck\w*|shit\w*|bastard|bitch|damn|asshole|slut|'
    r'cocaine|heroin|marijuana|hashish|opium|'
    r'murder\w*|slaughter\w*|corpse|suicide|behead\w*|'
    r'drunk\w*|drink\w*|drunken)\b', re.I)

def smutty(s, word):
    """句子里有没有不该有的内容。被考的那个词自己出现在黑名单里就不算（比如 drunk）"""
    for m in BADWORD.finditer(s):
        if m.group(0).lower() != word.lower():
            return True
    return False

# mid-sentence 出现的大写词多半是人名地名。CET6 例句里夹个人名，问她"这句在说什么"就跑偏了
def proper_nouns(s, keep):
    names = 0
    for i, t in enumerate(TOK.findall(s)):
        if i == 0:
            continue
        if t[:1].isupper() and t.lower() not in keep:
            names += 1
    return names

def score(s, word):
    """给候选句打分，越大越好。挑最短、最干净、最像教科书的。"""
    ts = TOK.findall(s)
    n = len(ts)
    sc = 0
    sc -= abs(n - 9) * 2                      # 9 个词的句子最好记，长了短了都扣
    sc -= proper_nouns(s, {word.lower()}) * 6
    sc -= len(re.findall(r'["“”\'‘’()]', s)) * 2
    sc -= len(re.findall(r'[;:—]', s)) * 2
    sc -= s.count(',')                        # 逗号多说明结构绕
    if s.endswith('?'):  sc -= 2              # 问句挖空后更难填
    if s.endswith('!'):  sc -= 1
    if ts and ts[0].lower() == word.lower(): sc -= 3   # 词在句首，上下文太少
    return sc

def cands_of(s):
    """句子里的实词集合（小写），用来给词表建倒排索引"""
    return {t.lower() for t in TOK.findall(s)}

def pick():
    words = load_words()
    targets = {w['word'].lower(): w['word'] for w in words}
    keep = {t.lower() for t in targets}

    files = sorted(DATA.glob('eng_sentences*.tsv.bz2')) + sorted(DATA.glob('eng*.tsv.bz2'))
    if not files:
        sys.exit('_data/ 里没有英文语料（eng_sentences.tsv.bz2）')
    src = files[0]

    # 一个词只留最好的 N 个候选，边读边淘汰，省内存
    KEEP = 6
    best = collections.defaultdict(list)
    seen = set()
    total = read = 0
    f = bz2.open(src, 'rt', encoding='utf-8', errors='replace')
    try:
        for line in f:
            total += 1
            parts = line.rstrip('\n').split('\t')
            if len(parts) < 3:
                continue
            s = parts[2].strip()
            if len(s) > 110 or len(s) < 18 or BADCH.search(s):
                continue
            ts = TOK.findall(s)
            if not (4 <= len(ts) <= 16):
                continue
            hit = cands_of(s) & keep
            if not hit:
                continue
            read += 1
            for w in hit:
                if w in seen and len(best[w]) >= KEEP:
                    continue
                # 目标词必须**整词出现且只出现一次**，不然挖空有歧义（挖哪一个？）
                if len(re.findall(r'\b' + re.escape(w) + r'\b', s, re.I)) != 1:
                    continue
                if smutty(s, w):
                    continue
                sc = score(s, w)
                L = best[w]
                if len(L) < KEEP:
                    L.append((sc, s))
                    L.sort(key=lambda x: -x[0])
                elif sc > L[-1][0]:
                    L[-1] = (sc, s)
                    L.sort(key=lambda x: -x[0])
    except (EOFError, OSError):
        # 下载被截断时 bz2 会在半路断掉。已经读到的部分照样能用，先出个初稿
        print('⚠ 语料读到头了（文件可能没下完），只用已读到的 %d 行' % total)
    finally:
        f.close()
    print('语料 %d 行，跟六级词表沾边的 %d 行' % (total, read))

    # 挑重复率：同一句被多个词共用就换下一档，尽量一题一句
    used = collections.Counter()
    for w, L in best.items():
        if L:
            used[L[0][1]] += 1
    out, miss = [], []
    for w in words:
        k = w['word'].lower()
        L = best.get(k) or []
        cand = None
        for sc, s in L:                      # 优先挑没被别的词占用的句子
            if used[s] <= 1:
                cand = s
                break
        if cand is None and L:
            cand = L[0][1]
        if cand is None:
            miss.append(w['word'])
            continue
        out.append((w['word'], cand))

    # 已有的译文要留住：中文是逐句翻出来的（贵），重挑一次英文句子不值得把它冲成 -
    old, _ = load_sents() if TXT.exists() else ({}, [])
    out.sort(key=lambda x: x[0].lower())
    kept = 0
    with io.open(TXT, 'w', encoding='utf-8', newline='') as f:
        f.write('# 句子练习例句。一行一句： 单词 | 英文句子 | 中文（可空，留空就写 -）\n')
        f.write('# 这是 _build_sents.py pick 生成的初稿，改完跑 inject。\n')
        f.write('# 挖空是 inject 时按「单词」那一列自动做的，别在句子里自己写 ___。\n')
        for w, s in out:
            prev = old.get(w.lower())
            zh = prev['zh'] if prev and prev['en'] == s and prev['zh'] else ''
            if zh:
                kept += 1
            f.write('%s | %s | %s\r\n' % (w, s, zh or '-'))
    print('写出 %d 句（%d 个词没找到合适例句，这些词只走英译中／中译英）；复用旧译文 %d 条'
          % (len(out), len(miss), kept))
    print('没例句的样本：', ', '.join(miss[:30]))

def load_sents():
    out, bad = {}, []
    if not TXT.exists():
        sys.exit('没有 原始数据/sentences.txt，先跑 pick')
    for i, line in enumerate(io.open(TXT, encoding='utf-8'), 1):
        line = line.rstrip('\n')
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        parts = [p.strip() for p in line.split('|')]
        if len(parts) != 3:
            bad.append('%d 行格式不对（要 word | 英文 | 中文）：%s' % (i, line))
            continue
        w, en, zh = parts
        if w.lower() in out:
            bad.append('%d 行 %s 重复了' % (i, w))
        out[w.lower()] = {'word': w, 'en': en, 'zh': '' if zh == '-' else zh}
    return out, bad

TR = BASE / '_tr'

def zh_merge():
    """把 _tr/out_*.tsv（`序号<TAB>中文`，分块翻译的产物）并回 sentences.txt 的第三列。

    序号是**数据行的行号**（0 起，跳过注释和空行），跟 _tr/in_*.tsv 是同一套——
    也就是说**重跑 pick 换过句子以后，序号就对不上了**，得重新导出再翻。
    分块文件 out_00.a.tsv…out_11.tsv 按文件名排序就是正确顺序（'.' < '1'）。
    """
    if not TR.exists():
        sys.exit('没有 _tr/ 目录，没什么可并的')
    zh, dup = {}, []
    for f in sorted(TR.glob('out_*.tsv')):
        for ln, line in enumerate(io.open(f, encoding='utf-8'), 1):
            line = line.rstrip('\r\n')
            if not line.strip():
                continue
            parts = line.split('\t')
            if len(parts) != 2 or not parts[0].strip().isdigit():
                sys.exit('%s 第 %d 行不是「序号<TAB>中文」：%s' % (f.name, ln, line[:60]))
            i, t = int(parts[0]), parts[1].strip()
            if not t:
                sys.exit('%s 第 %d 行译文是空的' % (f.name, ln))
            if i in zh and zh[i] != t:
                dup.append(i)                      # 序号重复且译文还不一样，不能瞎选一个
            zh[i] = t
    if dup:
        sys.exit('这些序号重复出现且译文不一致：%s' % dup[:10])

    raw = io.open(TXT, encoding='utf-8', newline='').read()
    lines = raw.split('\n')
    idx, hit, dirty = 0, 0, 0
    for n, line in enumerate(lines):
        cr = '\r' if line.endswith('\r') else ''
        body = line[:-1] if cr else line
        if not body.strip() or body.lstrip().startswith('#'):
            continue
        parts = [p.strip() for p in body.split('|')]
        if len(parts) != 3:
            sys.exit('sentences.txt 第 %d 行不是三列：%s' % (n+1, body[:60]))
        t = zh.pop(idx, None)
        if t is None:
            print('⚠ 第 %d 行（%s）没有译文，保持原样' % (idx, parts[0]))
        else:
            hit += 1
            if parts[2] != t:
                dirty += 1
            lines[n] = ' | '.join([parts[0], parts[1], t]) + cr
        idx += 1
    if zh:
        sys.exit('有 %d 个序号在 sentences.txt 里找不到对应行（前几个：%s），别硬并'
                 % (len(zh), sorted(zh)[:10]))
    io.open(TXT, 'w', encoding='utf-8', newline='').write('\n'.join(lines))
    print('并回 %d/%d 行，改动 %d 行' % (hit, idx, dirty))

def blank(en, word):
    """把词挖成 ___。生成时已经保证整词只出现一次，这里 count=1 兜底"""
    return re.sub(r'\b' + re.escape(word) + r'\b', '___', en, count=1, flags=re.I)

def check(S):
    words = {w['word'].lower(): w for w in load_words()}
    bad = {'词表没有': [], '词必现': [], '挖空失败': [], '太长': []}
    for k, v in S.items():
        if k not in words:
            bad['词表没有'].append(k)
            continue
        en, w = v['en'], v['word']
        if not re.search(r'\b' + re.escape(w) + r'\b', en, re.I):
            bad['词必现'].append('%s: %s' % (w, en))
            continue
        if blank(en, w) == en:
            bad['挖空失败'].append('%s: %s' % (w, en))
        if len(en) > 110:
            bad['太长'].append('%s: %s' % (w, en))
    return bad

def inject():
    S, fmt = load_sents()
    if fmt:
        print('格式有误，先修：')
        for x in fmt[:10]:
            print('   ', x)
        sys.exit(1)
    bad = check(S)
    n = sum(len(v) for v in bad.values())
    if n:
        print('对账没过：')
        for name, items in bad.items():
            if items:
                print('  %s %d' % (name, len(items)))
                for x in items[:5]:
                    print('     ', x)
        sys.exit(1)

    sents, trans = {}, {}
    for k, v in S.items():
        sents[k] = blank(v['en'], v['word'])
        if v['zh']:
            trans[k] = v['zh']
    html_path = BASE / 'index.html'
    html = html_path.read_text(encoding='utf-8')
    for name, obj in (('SENTS', sents), ('TRANS', trans)):
        blob = 'var %s = %s;' % (name, json.dumps(obj, ensure_ascii=False, separators=(',', ':')))
        html, cnt = re.subn(r'var %s = \{.*?\};' % name, lambda m, b=blob: b, html, count=1, flags=re.S)
        if cnt != 1:
            sys.exit('没找到 %s 块，index.html 结构变了' % name)
    html_path.write_text(html, encoding='utf-8')
    print('已注入 %d 条例句，其中 %d 条带中文翻译' % (len(sents), len(trans)))

if __name__ == '__main__':
    args = sys.argv[1:]
    if 'pick' in args:
        pick()
    elif 'zh-merge' in args:
        zh_merge()
    elif 'inject' in args:
        inject()
    else:
        sys.exit('用法：python _build_sents.py pick | zh-merge | inject')
