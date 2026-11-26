// Opens a gallery download, THM/thm_<Name>.tar, with RiptOPL's REAL theme-archive reader (src/platform/tar.cpp on
// the host) and checks that every file of the theme folder is found under the path the loaders build
// (<archive>/<file>) and reads back byte for byte. Usage: test_port_tar <theme.tar> <theme folder>
#include <dirent.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <stdlib.h>
#include <string>
#include <string.h>
#include <vector>
#include "src/platform/tar.cpp"
#include "check.h"
#include "kernel.h"

static std::string slurp(const std::string &path)
{
    FILE *f = fopen(path.c_str(), "rb");
    std::string s;
    if (!f) return s;
    char buf[65536];
    size_t n;
    while ((n = fread(buf, 1, sizeof(buf), f)) > 0) s.append(buf, n);
    fclose(f);
    return s;
}

int main(int argc, char **argv)
{
    if (argc != 3) { fprintf(stderr, "usage: %s theme.tar folder\n", argv[0]); return 2; }
    tarThemeInit();
    DIR *d = opendir(argv[2]);
    CHECK(d != NULL);
    int files = 0;
    for (struct dirent *e; d && (e = readdir(d));) {
        if (e->d_name[0] == '.') continue;
        // Repo-only files stay out of the .tar (tools/build_inventory.py TAR_EXCLUDE_RE).
        if (!strcmp(e->d_name, "theme.json") || !strcmp(e->d_name, "preview.png")) {
            std::string m = std::string(argv[1]) + "/" + e->d_name;
            void *b = NULL; int sz = 0;
            CHECK(tarThemeRead(m.c_str(), &b, &sz) == -1);
            continue;
        }
        std::string member = std::string(argv[1]) + "/" + e->d_name;
        CHECK(tarThemePath(member.c_str()) == 1);
        void *buf = NULL;
        int size = 0;
        int r = tarThemeRead(member.c_str(), &buf, &size);
        if (r != 1) { fprintf(stderr, "  not readable through the archive: %s (%d)\n", e->d_name, r); g_failures++; continue; }
        std::string want = slurp(std::string(argv[2]) + "/" + e->d_name);
        CHECK((size_t)size == want.size() && memcmp(buf, want.data(), want.size()) == 0);
        free(buf);
        files++;
    }
    if (d) closedir(d);
    CHECK(files > 0);
    std::string missing = std::string(argv[1]) + "/no_such_file.png";
    void *buf = NULL; int size = 0;
    CHECK(tarThemeRead(missing.c_str(), &buf, &size) == -1);
    tarThemeReset();
    printf("tar OK: %d files read back through %s\n", files, argv[1]);
    TEST_DONE("port tar");
}
