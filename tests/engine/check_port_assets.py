"""Byte- and block-level check of THM/thm_incebtion and THM/thm_korium against the pinned RiptOPL edition.
Usage: python3 tests/engine/check_port_assets.py /path/to/RiptOPL-with-history"""
import sys, re
from pathlib import Path
import os
ROOT=Path(__file__).resolve().parents[2]; os.chdir(ROOT); sys.path.insert(0,str(ROOT/'tools')); import port_builtin_theme as P
git=P.Git(Path(sys.argv[1]),P.PIN)
total=0
for t,spec in P.THEMES.items():
    bad=0
    src=P.AssetSource(git,spec['korium'])
    d=Path(f'THM/thm_{t}'); out=(d/'conf_theme.cfg').read_text()
    og,osecs=P.parse_cfg(out,'out'); gmap=dict(og)
    names={p.name for p in d.iterdir()}
    for view,path in spec['views'].items():
        text=P.korium_list(src) if (spec['korium'] and view=='list') else src.cfg(path).decode()
        g,secs=P.parse_cfg(text,view)
        pre='' if view=='list' else view+'.'
        secs=[(n,['default=APP_#Media' if l=='default=APP' else l for l in b]) for n,b in secs]  # porter step 5
        want={n:b for n,b in secs}
        got={n[len(pre):]:b for n,b in osecs if (n.startswith(pre) if pre else '.' not in n)}
        if want!=got:
            bad+=1; print(t,view,'BLOCK MISMATCH', sorted(set(want)^set(got))[:10])
            for n in want:
                if n in got and want[n]!=got[n]: print('  diff in',n)
        for k,v in g:
            if re.match(r'font\d',k): continue
            kk=(pre+k) if k in P.VIEW_GLOBALS else k
            if gmap.get(kk)!=v: bad+=1; print(t,view,'GLOBAL',k,v,gmap.get(kk))
        for fam in ('main','info'):
            idx=sorted(int(m.group(1)) for n in got for m in [re.fullmatch(fam+r'(\d+)',n)] if m)
            if idx and idx!=list(range(len(idx))): bad+=1; print(t,view,fam,'GAP',idx)
        # every asset referenced resolves to a shipped file
        for n,b in secs:
            for l in b:
                k,v=l.split('=',1)
                if k in('default','overlay','overlay2') and f'{v}.png' not in names: bad+=1; print(t,view,n,k,v,'NOT SHIPPED')
                if k=='attribute' and v in P.ATTRIBUTE_VALUES:
                    for val in P.ATTRIBUTE_VALUES[v]:
                        if f'{val}.png' in names and f'{val}_{v}.png' not in names: bad+=1; print('badge missing',val,v)
    # byte-identity: every texture equals what the edition embedded
    tbl=P.texture_table(git,spec['korium'])
    for name,stem in tbl:
        if name=='APP': continue  # porter step 5: not shipped, collides with app.png on FAT32
        f=d/f'{name}.png'
        if not f.exists():
            if name in P.ENGINE_READS: bad+=1; print(t,'ENGINE-READ TEXTURE MISSING',name)
            continue  # porter step 6: never opened from a disk theme, so not shipped
        if stem and f.read_bytes()!=src.png(stem): bad+=1; print(t,'BYTES DIFFER',name)
    for n in sorted(names):
        if n.endswith('.png') and n!='preview.png' and n[:-4] not in P.ENGINE_READS and not re.search(r'_(#?[A-Za-z]+)\.png$',n) \
           and n[:-4] not in {v.split('=',1)[1] for _,b in osecs for v in b if v.split('=',1)[0] in ('default','overlay','overlay2')}:
            bad+=1; print(t,'SHIPPED BUT NEVER READ',n)
    longest=max(len(f"{n}_{l.split('=',1)[0]}") for n,b in osecs for l in b)
    print(f"{t}: {'OK' if not bad else str(bad)+' PROBLEMS'} | {len(osecs)} blocks, {len(og)} globals, {len(names)} files, longest key {longest}/47")
    total+=bad
sys.exit(1 if total else 0)
