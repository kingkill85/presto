# MicroPython v1.26.0; NixOS: MKDIR=mkdir RM=rm
MPY_DIR ?= ../../../micropython
MOD = gbccore
# Keep objects from shared ../ sources inside the ignored build tree.
BUILD ?= build/audio
SRC = ../gbaudio/gbaudiocore.c ../gbaudio/vendor/minigb_apu.c ../common/mini_libc.c
ARCH = armv7emsp
CFLAGS_EXTRA = -O3 -fno-semantic-interposition -fno-strict-aliasing -std=gnu11 -Wno-unused-function -Wno-unused-variable -DNDEBUG
CFLAGS_EXTRA += -DGBC_AUDIO -DMINIGB_APU_AUDIO_FORMAT_S16SYS -DAUDIO_SAMPLE_RATE=22050
include ../common/flags.mk
include $(MPY_DIR)/py/dynruntime.mk

$(BUILD)/../gbaudio/gbaudiocore.o: gbccore.c $(wildcard vendor/*.c vendor/*.h) ../gbaudio/vendor/minigb_apu.h
