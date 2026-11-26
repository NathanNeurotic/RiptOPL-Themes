#!/bin/sh
# Engine-level checks for the ported themes, compiled against a RiptOPL checkout's REAL sources with ASan+UBSan
# (the same flags as RiptOPL's tests/host/run.sh). Usage: tests/engine/run.sh /path/to/RiptOPL [/path/to/history]
#   arg 1  a RiptOPL checkout (current engine: config.cpp, themeviews.cpp, tar.cpp)
#   arg 2  a RiptOPL clone holding the porter's pinned commit (default: arg 1)
set -e
here=$(cd "$(dirname "$0")/../.." && pwd)
rip=$(cd "${1:?RiptOPL checkout}" && pwd)
hist=${2:-$rip}
out=${TMPDIR:-/tmp}/riptopl-themes-engine
rm -rf "$out"; mkdir -p "$out"
CXX=${CXX:-g++}
FLAGS="-std=gnu++17 -g -O1 -Wall -Wextra -Wno-unused-parameter -Wno-write-strings -Wno-sign-compare -fsanitize=address,undefined -fno-sanitize-recover=undefined"
INC="-I$rip/tests/host/stub -I$rip/tests/host/stub/include -I$rip/tests/host -I$rip/include -I$rip"
"$CXX" $FLAGS $INC "$here/tests/engine/test_port_views.cpp" -o "$out/views"
"$CXX" $FLAGS $INC "$here/tests/engine/test_port_tar.cpp" -o "$out/tar"
python3 "$here/tools/build_inventory.py" --out _engine_site >/dev/null
fail=0
for t in incebtion korium; do
    python3 "$here/tools/port_builtin_theme.py" --riptopl "$hist" --theme "$t" --dump-sources "$out/$t" >/dev/null
    echo "== thm_$t"
    "$out/views" "$here/THM/thm_$t/conf_theme.cfg" "$out/$t/list.cfg" "$out/$t/coverflow.cfg" "$out/$t/psbbn.cfg" "$out/$t/grid.cfg" || fail=1
    "$out/tar" "$here/_engine_site/dl/thm_$t.tar" "$here/THM/thm_$t" || fail=1
done
rm -rf "$here/_engine_site"
python3 "$here/tests/engine/check_port_assets.py" "$hist" || fail=1
exit $fail
