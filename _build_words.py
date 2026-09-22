# 把 原始数据/cet4.txt + cet6.txt 解析出来灌进 index.html 的 WORDS 常量。
#   python _build_words.py
# 源格式（mahavivo/english-wordlists 的 CET4_edited.txt / CET6_edited.txt）：
#   abandon [əˈbændən] v. 1. 抛弃，放弃 2. 离弃(家园、船只、飞机等)
#
# 两个表有 1014 个词重叠，所以合并成**一个**数组，每个词带 lv：
#   lv='4' 只在四级   lv='6' 只在六级   lv='46' 两边都有
# 重叠的词只留一份，释义取**四级**那份（更短，起步的人看着不累），只把级别并上。
#
# id 用单词本身（小写）而不是下标 —— 这样以后加词、改顺序，学习进度都不会错位。
# 一个词要两份释义：
#   full —— 完整释义，答题后展示
#   cn   —— 只留第一个义项，四选一里当选项用（太长或带编号的选项没法看）
import json, io, re, sys, pathlib

sys.stdout.reconfigure(encoding='utf-8')
BASE = pathlib.Path(__file__).parent
SRC  = BASE / '原始数据'

# 先四级后六级：重叠的词会留先解析到的那份，也就是四级
SOURCES = [('4', 'cet4.txt'), ('6', 'cet6.txt')]

# 词性标记。长的排前面，不然 "adj." 会被 "a." 抢先匹配掉半截。
# 前面加 (?<![A-Za-z]) 才不会在单词内部乱匹配（比如 "analysis" 里的 n）
POS = r'(?<![A-Za-z])(?:abbr|adj|adv|aux|art|conj|pron|prep|num|int|vt|vi|ad|a|n|v)[.·]'
CJK = r'一-鿿'

def norm(s):
    # 词表里混了一批形近字，音标得换回真 IPA：
    #   ә(U+04D9 西里尔) 冒充 ə、ү 冒充 ʌ、є(U+0454) 冒充 ɛ
    #   ∫(U+222B 积分号！) 其实是 Symbol 字体的 ʃ —— 有 496 处，不换音标就是错的
    s = (s.replace('ә', 'ə').replace('ү', 'ʌ').replace('Ә', 'Ə')
          .replace('є', 'ɛ').replace('∫', 'ʃ')
          .replace('', ']').replace('', '[')   # 私用区里伪装的方括号
          .replace('‚', "'").replace(' ', ' ').replace('﻿', ''))
    # 那对私用区括号常跟真的方括号**叠在一起**（"…ˈlaitniŋ]]n.闪电"），叠了就留一个
    s = re.sub(r'\]\]', ']', s)
    s = re.sub(r'\[\[', '[', s)
    return s.strip()

def has_cn(s):
    return re.search('[' + CJK + ']', s) is not None

def parse(line):
    line = norm(line)
    if not line:
        return None

    ph, dfn = '', ''
    m = re.match(r'^(.+?)\s*\[(.+?)\]\s*(.*)$', line)          # word [音标] 释义
    if m:
        w, txt, dfn = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
        ph = '/' + txt + '/'
    else:
        # 兜底：抓行首单词，从第一个词性标记开始全算释义，中间那块找音标。
        # 源里有 "arbitrary ˈɑːbɪtrərɪ /adj. ..." 这种少了个左括号的残行
        m = re.match(r"^([A-Za-z][A-Za-z\-'.]*)\s+(.*)$", line)
        if not m:
            return None
        w, tail = m.group(1), m.group(2)
        d = re.search(POS, tail)
        if not d:
            return None
        # 音标块找重音符；没有重音符的（"drɑːft"）就退而求其次取第一个词
        pre = tail[:d.start()].strip().strip('/').strip()
        dm = re.search(r'[^\s/]*[ˈˌ][^\s/]*', pre) or re.match(r'\S+', pre)
        ph = '/' + dm.group(0) + '/' if dm and not re.match(r'^[A-Za-z]{1,3}[.·]$', dm.group(0)) else ''
        dfn = tail[d.start():].strip()

    # "attribute 1"/"boom 2" 这种同形词，编号只是区分词性，并成一个词
    w = re.sub(r'\s+\d+$', '', w).strip()
    w = re.sub(r'\([^)]*\)$', '', w).strip()   # "toward(s)"→"toward"、"systematic(al)"→"systematic"
    if not re.match(r"^[A-Za-z][A-Za-z\-'. ]*$", w) or not dfn:
        return None

    # "|| 短语搭配"那半截英文中文挤在一起没空格，排版救不回来，不要了
    dfn = re.split(r'\s*\|\|\s*', dfn)[0].strip()
    # 音标后面常缀个逗号（"hundred [..], num.百，百个"），先削掉
    dfn = re.sub(r'^[,，.、;；]\s*', '', dfn)
    # "prep&conj."、"a.&ad." 这种链式词性，把中间的 & 补成句点，后面才好一条条剥
    dfn = re.sub(r'(?<![A-Za-z])([a-z]{1,5})&(?=[a-z]{1,5}[.·])', r'\1. ', dfn)
    # 单复数提示可能夹在音标和词性之间：(pl analyses) n. ... / （pl criteria) n. ...
    dfn = re.sub(r'^[（(][^)）]*\b(?:pl|sing)\b[^)）]*[)）]\s*', '', dfn)
    if not dfn or not has_cn(dfn):
        return None

    # ---- full：编号换成「；」当义项分隔，保留词性标记 ----
    full = re.sub(r'\s+', ' ', dfn).strip()
    full = re.sub(r'^((?:' + POS + r'))\s*\d+[\.、]\s*', r'\1 ', full)     # "v. 1. xxx" → "v. xxx"
    full = re.sub(r'\s*(' + POS + r')\s*', lambda m: ' ' + m.group(1) + ' ', full)
    full = re.sub('(?<=[' + CJK + r'\)])\s*\d+[\.、]\s*', '；', full)        # 中文后的 " 2. " → ；
    full = re.sub(r'\s*[;；]\s*', '；', full)
    full = re.sub(r'\s+', ' ', full).strip(' ；')
    # full 里保留派生词（学一个词顺带认一家子，有价值），但不能糊成一团："的financially"
    full = re.sub(r'[（(][^)）]*[A-Za-z=][^)）]*[)）]', '', full)
    full = re.sub('(?<=[' + CJK + r'])([A-Za-z]{2,})', r' \1', full)
    full = re.sub(r'\s+', ' ', full).strip(' ；')
    # 释义太长的（有的能到 90 字）在反馈页会糊成一片，切到最后一个完整义项为止
    if len(full) > 60:
        cut = [i for i, c in enumerate(full[:60]) if c == '；']
        full = (full[:cut[-1]] if cut else full[:60]) + '…'
    if not full:
        return None

    # ---- cn：先砍到第一个词性为止，再砍到第二个义项为止，剩下的才是"第一个义项" ----
    # 开头的词性可能有好几个连着写（"v. &n."、"n. & v."），一直剥到没有为止
    body = dfn
    # 开头夹着 "(缩作 OK)" 这类提示时先削掉，不然紧接着的词性剥不掉
    body = re.sub(r'^[（(][^)）]{0,24}[)）][\s&]*(?=' + POS + r')', '', body)
    while True:
        new = re.sub(r'^[\s&]*(?:' + POS + r')[\s&]*', '', body)
        if new == body:
            break
        body = new
    body = re.split(r'[\s&]*' + POS + r'[\s&]*', body)[0]      # 后面还有别的词性就砍掉
    # 剥完词性后紧跟着的可能是单复数提示：(pl analyses)、(sing &pl)
    body = re.sub(r'^[（(][^)）]*\b(?:pl|sing)\b[^)）]*[)）]\s*', '', body)
    body = re.sub(r'^\s*\d+[\.、]\s*', '', body)           # 去掉开头的 "1."
    body = re.split(r'\s+\d+[\.、]\s*', body)[0]           # 砍到第二个义项
    body = re.split(r'\s*[;；]\s*', body)[0]
    cn = re.sub(r'\s+', '', body).strip('，,。.;；、 ')
    # 选项里带括号不好读（"(生物)种"、"（使）破裂"），去掉了意思还在
    stripped = re.sub(r'^[（(][^)）]*[)）]', '', cn)
    if has_cn(stripped):
        cn = stripped
    # 尾巴上常缀着英文：派生词（"财政的，金融的financially"）、对照词（"楼梯间(=stairway)"）。
    # 四选一的选项里出现英文很难看，砍掉
    t = re.sub(r'[（(][^)）]*[A-Za-z=][^)）]*[)）]', '', cn)
    if has_cn(t):          # "(can 的过去式)" 整条都在括号里，削完就空了，留着
        cn = t
    am = re.search(r'(?<![A-Za-z])[A-Za-z]{3,}', cn)
    if am and has_cn(cn[:am.start()]):
        cn = cn[:am.start()].strip('，,。.;；、 ')
    if not cn or not has_cn(cn):
        return None
    if len(cn) > 18:                                        # 还是太长就按逗号切到能看的长度
        for cut in re.split(r'[，,]', cn):
            if 1 < len(cut) <= 18:
                cn = cut
                break
        else:
            cn = cn[:18]
    return {'word': w, 'cn': cn, 'full': full, 'phonetic': ph}

words, seen, bad = [], {}, []
for lv, fname in SOURCES:
    path = SRC / fname
    if not path.exists():
        sys.exit('缺 %s' % path)
    for line in io.open(path, encoding='utf-8'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        p = parse(line)
        if not p:
            if re.search(r'[A-Za-z]', line):     # 纯标题/字母分节行不算错
                bad.append((fname, line))
            continue
        k = p['word'].lower()
        old = seen.get(k)
        if old is None:
            p['lv'] = lv
            seen[k] = p
            words.append(p)
        elif lv in old['lv']:
            # 同一个表里的同形词（verb 义 + noun 义）合并：full 拼起来，cn 留第一条
            if p['full'] not in old['full']:
                old['full'] = (old['full'] + ' ' + p['full']).strip()
            if not old['phonetic']:
                old['phonetic'] = p['phonetic']
        else:
            # 跨表重叠：释义保留已解析的那份（四级，更简短），只把级别并上
            old['lv'] = ''.join(sorted(set(old['lv'] + lv)))
            if not old['phonetic']:
                old['phonetic'] = p['phonetic']

if not words:
    sys.exit('一个词都没解析出来')

for w in words:
    w['id'] = w['word'].lower()

# id 要当 localStorage 的键、还要进 HTML 属性，有引号/重复就炸，宁可这里先死
ids = [w['id'] for w in words]
dupes = [k for k, n in __import__('collections').Counter(ids).items() if n > 1]
if dupes:
    sys.exit('id 重复：%s' % dupes[:5])
weird = [w['word'] for w in words if re.search(r'["\'<>&]', w['word'])]
if weird:
    sys.exit('词里有引号或尖括号，当 id 不安全：%s' % weird[:5])

# 键顺序固定下来，将来 diff 才看得清
out = [{'id': w['id'], 'word': w['word'], 'phonetic': w['phonetic'], 'lv': w['lv'],
        'cn': w['cn'], 'full': w['full']} for w in words]

from collections import Counter
dup = [c for c, n in Counter(w['cn'] for w in out).items() if n > 1]

blob = 'var WORDS = ' + json.dumps(out, ensure_ascii=False, separators=(',', ':')) + ';'
p = BASE / 'index.html'
html = p.read_text(encoding='utf-8')
# WORDS 是单独一行，用 [^\n] 卡死，别让它误吞后面的 SENTS
new, n = re.subn(r'var WORDS = \[[^\n]*\];', lambda m: blob, html, count=1)
if n != 1:
    sys.exit('没找到 WORDS 块，index.html 结构变了')
p.write_text(new, encoding='utf-8')

by_lv = Counter(w['lv'] for w in out)
print('灌入 %d 词' % len(out))
print('  四级独有 %d · 六级独有 %d · 两边都有 %d' % (by_lv['4'], by_lv['6'], by_lv['46']))
print('无音标 %d 个，同释义组 %d 组' % (sum(1 for w in out if not w['phonetic']), len(dup)))
if bad:
    print('解析不了 %d 行，前 8 条：' % len(bad))
    for f, x in bad[:8]:
        print('   [%s] %s' % (f, x))
print('样本：')
for w in out[:3] + out[2200:2202] + out[-2:]:
    print('   %-14s %-16s lv=%-2s | %-12s | %s' % (w['word'], w['phonetic'], w['lv'], w['cn'], w['full'][:44]))
