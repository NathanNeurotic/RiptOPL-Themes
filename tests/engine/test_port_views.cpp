// Runs a ported theme's conf_theme.cfg through RiptOPL's REAL config parser and multi-view resolver
// (src/core/config.cpp + src/gfx/themeviews.cpp, compiled on the host) and checks that, in every view, every
// family slot resolves to a block whose keys are identical to the block the built-in edition loaded from that
// view's own cfg file. Usage: test_port_views <merged.cfg> <list.cfg> <coverflow.cfg> <psbbn.cfg> <grid.cfg>
#include <map>
#include <string>
#include <string.h>
#include "src/platform/util.cpp"
#include "src/core/config.cpp"
#include "src/gfx/themeviews.cpp"
#include "host_env.h"
#include "check.h"

static config_set_t *load(const char *path)
{
    FILE *f = fopen(path, "rb");
    if (!f) { fprintf(stderr, "cannot open %s\n", path); exit(2); }
    std::string text;
    char buf[4096];
    size_t n;
    while ((n = fread(buf, 1, sizeof(buf), f)) > 0)
        text.append(buf, n);
    fclose(f);
    config_set_t *c = configAlloc(0, NULL, NULL);
    configReadBuffer(c, text.data(), (int)text.size());
    return c;
}

static std::map<std::string, std::string> keysOf(config_set_t *c, const std::string &block)
{
    std::map<std::string, std::string> out;
    std::string p = block + "_";
    for (const config_value_t *it = c->entries(); it; it = it->next)
        if (!strncmp(it->key, p.c_str(), p.size()))
            // The porter's one deliberate change (tools/port_builtin_theme.py, 5. Case): default=APP -> APP_#Media.
            out[it->key + p.size()] = (!strcmp(it->key + p.size(), "default") && !strcmp(it->val, "APP_#Media")) ? "APP" : it->val;
    return out;
}

struct Family { const char *name; const char *chain[4]; int len; };
static const Family families[] = {
    {"main", {"main"}, 1}, {"info", {"info"}, 1},
    {"appsMain", {"appsMain", "main"}, 2}, {"appsInfo", {"appsInfo", "info"}, 2},
    {"vcdMain", {"vcdMain", "appsMain", "main"}, 3}, {"vcdInfo", {"vcdInfo", "info"}, 2},
    {"favsMain", {"favsMain", "main"}, 2}, {"favsInfo", {"favsInfo", "info"}, 2},
    {"favsVcdMain", {"favsVcdMain", "vcdMain", "appsMain", "main"}, 4}, {"favsVcdInfo", {"favsVcdInfo", "vcdInfo", "info"}, 3},
    {"favsAppsMain", {"favsAppsMain", "favsMain", "main"}, 3}, {"favsAppsInfo", {"favsAppsInfo", "favsInfo", "info"}, 3},
};

int main(int argc, char **argv)
{
    if (argc != 6) { fprintf(stderr, "usage: %s merged list coverflow psbbn grid\n", argv[0]); return 2; }
    config_set_t *merged = load(argv[1]);
    const int order[4] = {THM_VIEW_LIST, THM_VIEW_COVERFLOW, THM_VIEW_PSBBN, THM_VIEW_GRID};
    thm_view_info_t info;
    thmViewScan(merged, &info);
    CHECK(info.mask == 0xFu);                 // all four views offered
    CHECK(info.defaultView == THM_VIEW_LIST); // List until the user picks
    int slots = 0, mismatches = 0;
    for (int i = 0; i < 4; i++) {
        int v = order[i];
        config_set_t *src = load(argv[2 + i]);
        const char *prefix = thmViewPrefix(&info, v);
        int inherit = thmViewInheritsBase(&info, v);
        CHECK(inherit == (v == THM_VIEW_LIST)); // every non-list view is self-contained, like its built-in file
        for (const Family &f : families) {
            for (int j = 0; j < 64; j++) {
                char a[THM_VIEW_BLOCK_NAME_LEN], b[THM_VIEW_BLOCK_NAME_LEN];
                int ra = thmViewResolveSlot(merged, prefix, inherit, f.chain, f.len, j, a, sizeof(a));
                int rb = thmViewResolveSlot(src, "", 1, f.chain, f.len, j, b, sizeof(b));
                if (ra != rb) { fprintf(stderr, "%s %s%d: present %d vs edition %d\n", thmViewName(v), f.name, j, ra, rb); mismatches++; continue; }
                if (!ra) continue;
                slots++;
                if (keysOf(merged, a) != keysOf(src, b)) { fprintf(stderr, "%s %s%d: %s differs from edition %s\n", thmViewName(v), f.name, j, a, b); mismatches++; }
            }
        }
        for (const char *k : {"use_real_height", "use_default", "coverflow_cover_offset"}) {
            int want, got;
            if (configGetInt(src, k, &want)) {
                CHECK(thmViewGetInt(merged, prefix, k, &got) && got == want);
            }
        }
        int lct = 1, want = 1;
        configGetInt(src, "list_cfg_text", &want);
        thmViewGetInt(merged, prefix, "list_cfg_text", &lct);
        CHECK(lct == want);
        configFree(src);
    }
    CHECK(mismatches == 0);
    printf("views OK: %d resolved slots across 4 views match the edition\n", slots);
    configFree(merged);
    TEST_DONE("port views");
}
