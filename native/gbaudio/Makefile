MPY_DIR ?= ../../../micropython
MOD = gbaudiocore
SRC = gbaudiocore.c vendor/minigb_apu.c ../common/mini_libc.c
ARCH = armv7emsp
CFLAGS_EXTRA = -O2 -std=gnu11 -Wno-error -Wno-unused-function -Wno-unused-variable -DMINIGB_APU_AUDIO_FORMAT_S16SYS -DAUDIO_SAMPLE_RATE=22050
include ../common/flags.mk
include $(MPY_DIR)/py/dynruntime.mk

$(BUILD)/gbaudiocore.o: ../gb/gbcore.c ../gb/peanut_gb.h vendor/minigb_apu.h
