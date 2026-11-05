// SPDX-License-Identifier: GPL-2.0-or-later
// Explicit, tested game profiles; not a general ScummVM detector.
#include "common/config-manager.h"
#include "common/archive.h"
#include "common/fs.h"
#include "base/plugins.h"
#include "backends/platform/rp2350/rp2350-system.h"
#include "scumm/scumm_v5.h"
#include "scumm/scumm_v4.h"
#include "scumm/detection.h"
#include "audio/mididrv.h"
#include "runtime.h"
#include <new>

void *operator new(size_t n) {
    void *p = malloc(n);
    if (!p) scumm_runtime_fail("SCUMM arena exhausted");
    return p;
}
void *operator new[](size_t n) { return ::operator new(n); }
void operator delete(void *p) noexcept { free(p); }
void operator delete[](void *p) noexcept { free(p); }
void operator delete(void *p, size_t) noexcept { free(p); }
void operator delete[](void *p, size_t) noexcept { free(p); }
extern "C" void __cxa_pure_virtual() { scumm_runtime_fail("SCUMM pure virtual call"); }

Engine *presto_active_engine = nullptr;
extern "C" int scumm_engine_state(int op, int slot) {
    if (!presto_active_engine) return 0;
    if (op == 0) return (presto_active_engine->canSaveGameStateCurrently() ? 1 : 0)
                      | (presto_active_engine->canLoadGameStateCurrently() ? 2 : 0);
    if (slot < 1 || slot > 5) return -1;
    if (op == 1 && presto_active_engine->canSaveGameStateCurrently())
        return presto_active_engine->saveGameState(slot, "Presto slot").getCode() == Common::kNoError ? 1 : -1;
    if (op == 2 && presto_active_engine->canLoadGameStateCurrently())
        return presto_active_engine->loadGameState(slot).getCode() == Common::kNoError ? 1 : -1;
    return -1;
}

extern "C" int scumm_engine_run(const char *path, int profile) {
    const bool monkey = profile == 1;
    // One engine session per soft reset: engine globals/singletons contain
    // arena pointers. The Python launcher resets after exit or failure.
    ConfMan.setActiveDomain(monkey ? "presto-monkey-vga-de" : "presto-monkey2-de");
    ConfMan.set("path", path);
    const char *false_keys[] = {"confirm_exit", "enable_unsupported_game_warning",
        "native_mt32", "enable_gs", "multi_midi", "aspect_ratio", "fullscreen",
        "filtering", "copy_protection", "dump_scripts", "demo_mode", "nosubtitles", "mute", "music_mute", "sfx_mute"};
    for (auto key : false_keys) ConfMan.setBool(key, false);
    const char *true_keys[] = {"speech_mute",
        "subtitles", "object_labels"};
    for (auto key : true_keys) ConfMan.setBool(key, true);
    ConfMan.setInt("autosave_period", 0);
    ConfMan.setInt("music_volume", 192);
    ConfMan.setInt("sfx_volume", 192);
    ConfMan.setInt("speech_volume", 0);
    ConfMan.setInt("talkspeed", 60);
    ConfMan.setInt("midi_gain", 100);
    // MI2's original boot-script entry avoids the numeric recipe prompt on
    // a controller-only device. The upstream engine documents this value.
    ConfMan.setInt("boot_param", monkey ? 0 : 10001);
    ConfMan.setInt("save_slot", -1);
    ConfMan.setInt("dimuse_tempo", 10);
    ConfMan.setInt("tempo", 0);
    ConfMan.set("music_driver", "adlib");
    ConfMan.set("gm_device", "null");
    ConfMan.set("mt32_device", "null");
    ConfMan.set("language", "de");
    ConfMan.set("gfx_mode", "normal");
    ConfMan.set("render_mode", "");
    ConfMan.set("easter_egg", "");
    ConfMan.set("gameid", monkey ? "monkey" : "monkey2");
    ConfMan.set("original_gui", "false");
    ConfMan.set("savepath", "/sd/scumm/saves");
    g_system = new OSystem_RP2350();
    g_system->initBackend();
    PluginManager::instance().loadAllPlugins();
    Common::FSNode directory(path);
    if (!directory.exists() || !directory.isDirectory())
        scumm_runtime_fail("SCUMM game directory missing");
    SearchMan.addDirectory(path, directory, 0, 2);
    Scumm::DetectorResult dr = {};
    dr.fp.pattern = monkey ? "%03d.LFL" : "monkey2.%03d";
    dr.fp.genMethod = monkey ? Scumm::kGenRoomNum : Scumm::kGenDiskNum;
    dr.game.gameid = monkey ? "monkey" : "monkey2";
    dr.game.variant = monkey ? "VGA" : "";
    dr.game.id = monkey ? Scumm::GID_MONKEY_VGA : Scumm::GID_MONKEY2;
    dr.game.version = monkey ? 4 : 5;
    dr.game.midi = MDT_PCSPK | MDT_ADLIB | MDT_MIDI | MDT_PREFER_MT32;
    if (monkey) dr.game.midi |= MDT_PCJR | MDT_CMS;
    dr.game.platform = Common::kPlatformDOS;
    dr.game.guioptions = "";
    dr.language = Common::DE_DEU;
    // ScummEngine reads all 32 characters unconditionally. Never pass an
    // empty MD5 string; the Python launcher validates these exact data sets.
    dr.md5 = monkey ? "d0b531227a27c6662018d2bd05aac52a" : "6886e5d08cee329b1f2e743ae2e3ceed";
    dr.extra = monkey ? "VGA" : "";
    printf("SCUMM: creating v%d engine for %s\n", dr.game.version, dr.game.gameid);
    Engine *engine = monkey ? static_cast<Engine *>(new Scumm::ScummEngine_v4(g_system, dr))
                            : static_cast<Engine *>(new Scumm::ScummEngine_v5(g_system, dr));
    printf("SCUMM: running %s\n", dr.game.gameid);
    presto_active_engine = engine;
    Common::Error result = engine->run();
    presto_active_engine = nullptr;
    printf("SCUMM: engine returned %d\n", result.getCode());
    delete engine;
    delete static_cast<OSystem_RP2350 *>(g_system);
    g_system = nullptr;
    return result.getCode();
}
