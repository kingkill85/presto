# Build: make MPY_DIR=/path/to/micropython (v1.26.0, like the firmware)
# On NixOS add MKDIR=mkdir RM=rm (dynruntime.mk wants /bin/mkdir).
MPY_DIR ?= ../../../micropython
MOD = gbcore
SRC = gbcore.c ../common/mini_libc.c
ARCH = armv7emsp
CFLAGS_EXTRA = -O2 -std=gnu11 -Wno-error -Wno-unused-function -Wno-unused-variable
include ../common/flags.mk
include $(MPY_DIR)/py/dynruntime.mk
