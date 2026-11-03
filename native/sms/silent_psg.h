// Audio is intentionally disabled, like the existing Game Boy app.
// Preserve the PSG-facing API so CPU/VDP timing is unchanged without a mixer.
#include "vendor/sn76489.h"
struct Sn76489 { int unused; };
struct Sn76489 silent_psg;
Sn76489 *psg_init(double clock, double rate) { return &silent_psg; }
void psg_quit(Sn76489 *p) {}
void psg_reset(Sn76489 *p, unsigned a, unsigned b) {}
void psg_write_io(Sn76489 *p, unsigned value, unsigned time) {}
void psg_gg_write_io(Sn76489 *p, unsigned value, unsigned time) {}
void psg_set_channel_volume(Sn76489 *p, unsigned channel, float volume) {}
void psg_set_master_volume(Sn76489 *p, float volume) {}
void psg_update_timestamp(Sn76489 *p, int time) {}
void psg_end_frame(Sn76489 *p, unsigned time) {}
int psg_samples_avaliable(const Sn76489 *p) { return 0; }
int psg_read_samples(Sn76489 *p, short out[], int count) { return 0; }
void psg_clear_samples(Sn76489 *p) {}
unsigned psg_state_size(const Sn76489 *p, int include_blip) { return 0; }
int psg_save_state(const Sn76489 *p, void *data, unsigned size, int blip) { return 0; }
int psg_load_state(Sn76489 *p, const void *data, unsigned size, int blip) { return 0; }
