// SPDX-License-Identifier: GPL-2.0-or-later
// Exercise the upstream SCUMM BOMP decoder through the native C++ ABI.
// The encoded bytes below are an original synthetic test, not game assets.
#include "scumm/bomp.h"
extern "C" int scumm_bomp_probe(void) {
    const byte encoded[] = {7, 42, 6, 1, 2, 3, 4};
    const byte expected[] = {42, 42, 42, 42, 1, 2, 3, 4};
    byte decoded[8] = {};
    Scumm::bompDecodeLine(decoded, encoded, 8);
    for (int i = 0; i < 8; ++i) {
        if (decoded[i] != expected[i]) return 0;
    }
    // Reverse decoding places runs right-to-left; literal runs keep their order.
    const byte reverse_expected[] = {1, 2, 3, 4, 42, 42, 42, 42};
    Scumm::bompDecodeLineReverse(decoded, encoded, 8);
    for (int i = 0; i < 8; ++i) {
        if (decoded[i] != reverse_expected[i]) return 0;
    }
    return 1;
}
