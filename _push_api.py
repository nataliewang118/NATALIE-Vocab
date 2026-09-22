# 这台机器上 github.com 被墙，git push 走不通（api.github.com 反而通）。
# 所以把本地已提交的内容通过 Git Data API 推上去。
#
# ponytail: 只做"把当前 HEAD 推成一条 commit"，不做增量/历史，够用就行。
# 只推 master。空仓库要先播种（GitHub 不让在空仓库上建 blob），再改名成 master。
import base64, json, subprocess, sys, urllib.error, urllib.request
sys.stdout.reconfigure(encoding='utf-8')

REPO = 'nataliewang118/NATALIE-Vocab'
BRANCH = 'master'
GH = r'C:\Program Files\GitHub CLI\gh.exe'
TOKEN = subprocess.check_output([GH, 'auth', 'token'], text=True).strip()


def api(method, path, body=None):
    req = urllib.request.Request(
        'https://api.github.com' + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Authorization': 'Bearer ' + TOKEN,
                 'Accept': 'application/vnd.github+json',
                 'Content-Type': 'application/json',
                 'User-Agent': 'cet6-push'})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.load(r) if r.status != 204 else None
    except urllib.error.HTTPError as e:
        if e.code in (404, 409):  # 404/409 = 没有，不是出错
            return None
        print('  HTTP', e.code, e.read().decode()[:300])
        raise


# 1) 空仓库先播种，否则建 blob 会 409。
#    注意别信 repo['size']——它是懒更新的，播种完还是 0。看分支存不存在才准。
default = api('GET', f'/repos/{REPO}')['default_branch']
cur = api('GET', f'/repos/{REPO}/git/ref/heads/{BRANCH}') or \
      api('GET', f'/repos/{REPO}/git/ref/heads/{default}')
if cur is None:
    api('PUT', f'/repos/{REPO}/contents/.gitignore',
        {'message': 'init', 'content': base64.b64encode(b'__pycache__/\n').decode()})
    cur = api('GET', f'/repos/{REPO}/git/ref/heads/{default}')
    print('  空仓库，已播种')

# 2) 本地 HEAD 的全部文件（内容直接取 git 对象，跟本地 commit 完全一致）
#    quotepath=false：不然中文路径会被转义成 "\345\216\237..."，建出来是乱码路径
log = subprocess.check_output(['git', '-c', 'core.quotepath=false',
                               'ls-tree', '-r', 'HEAD'], text=True)
entries = []
for line in log.splitlines():
    meta, path = line.split('\t', 1)
    mode, _, sha = meta.split()
    content = base64.b64encode(subprocess.check_output(['git', 'cat-file', 'blob', sha])).decode()
    entries.append({'path': path, 'mode': mode, 'type': 'blob',
                    'sha': api('POST', f'/repos/{REPO}/git/blobs',
                               {'content': content, 'encoding': 'base64'})['sha']})
print('  文件', len(entries), '个')

# 3) 打一条 commit
tree = api('POST', f'/repos/{REPO}/git/trees', {'tree': entries})
commit = api('POST', f'/repos/{REPO}/git/commits',
             {'message': subprocess.check_output(['git', 'log', '-1', '--pretty=%B'],
                                                 text=True).strip(),
              'tree': tree['sha'], 'parents': [cur['object']['sha']] if cur else []})

# 4) 落到 master，并把默认分支掰成 master、删掉播种用的 main
if cur and cur['ref'].endswith('/' + BRANCH):
    api('PATCH', f'/repos/{REPO}/git/refs/heads/{BRANCH}', {'sha': commit['sha']})
else:
    api('POST', f'/repos/{REPO}/git/refs',
        {'ref': f'refs/heads/{BRANCH}', 'sha': commit['sha']})
    api('PATCH', f'/repos/{REPO}', {'default_branch': BRANCH})
    api('DELETE', f'/repos/{REPO}/git/refs/heads/{default}')

# 不用给本地记 origin/master：那边的 commit 对象本地没有，ref 指不过去。
print('已推送', commit['sha'][:10], '到', BRANCH)
