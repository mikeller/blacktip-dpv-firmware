# ruff: noqa: S101
import os
import re
import pathlib
import pytest

# Note: Using pytest (discovered in repo) for readability and richer assertions.

MAKEFILE = os.environ.get("MAKEFILE_PATH", "Makefile")

@pytest.fixture(scope="module")
def make_text():
    path = pathlib.Path(MAKEFILE)
    if not path.exists():
        pytest.skip(f"Makefile not found at {MAKEFILE}")
    return path.read_text(encoding="utf-8", errors="ignore")

def test_project_name_is_set(make_text):
    assert re.search(r'^\s*PROJECT\s*=\s*BLDC_4_ChibiOS\s*$', make_text, re.M) is not None, \
        "PROJECT should be BLDC_4_ChibiOS"

def test_chibios_version_pin(make_text):
    assert re.search(r'^\s*CHIBIOS\s*=\s*ChibiOS_3\.0\.5\s*$', make_text, re.M), \
        "CHIBIOS should be set to ChibiOS_3.0.5"

def test_use_lispbm_default_disabled(make_text):
    assert re.search(r'^\s*USE_LISPBM\s*=\s*0\s*$', make_text, re.M), \
        "USE_LISPBM should default to 0 (disabled)"

def test_lispbm_blocks_present_when_enabled(make_text):
    # When USE_LISPBM==1, we expect includes and flags
    assert re.search(r'(?ms)^\s*ifeq\s*\(\$\(USE_LISPBM\),1\)\s*\n\s*include\s+lispBM/lispbm\.mk\s*\n\s*USE_OPT\s*\+\=\s*-DUSE_LISPBM\s*\n\s*endif', make_text), \
        "Conditional block for lispBM include and USE_OPT += -DUSE_LISPBM missing"
    # CSRC and INCDIR augmentations
    assert re.search(r'(?ms)^\s*ifeq\s*\(\$\(USE_LISPBM\),1\)\s*\n\s*CSRC\s*\+\=\s*\$\(LISPBMSRC\)\s*\n\s*endif', make_text), \
        "Conditional CSRC += $(LISPBMSRC) block missing"
    assert re.search(r'(?ms)^\s*ifeq\s*\(\$\(USE_LISPBM\),1\)\s*\n\s*INCDIR\s*\+\=\s*\$\(LISPBMINC\)\s*\n\s*endif', make_text), \
        "Conditional INCDIR += $(LISPBMINC) block missing"

def test_link_time_and_gc_defaults(make_text):
    # USE_LINK_GC defaults to yes
    assert re.search(r'^\s*USE_LINK_GC\s*=\s*yes\s*$', make_text, re.M), "USE_LINK_GC should default to yes"
    # USE_LTO defaults to no
    assert re.search(r'^\s*USE_LTO\s*=\s*no\s*$', make_text, re.M), "USE_LTO should default to no"

def test_thumb_and_fpu_settings(make_text):
    assert re.search(r'^\s*USE_THUMB\s*=\s*yes\s*$', make_text, re.M), "USE_THUMB should be yes"
    assert re.search(r'^\s*USE_FPU\s*=\s*hard\s*$', make_text, re.M), "USE_FPU should be hard"

def test_warning_flags(make_text):
    cwarn = re.search(r'^\s*CWARN\s*=\s*(.+)$', make_text, re.M)
    assert cwarn, "CWARN line missing"
    flags = cwarn.group(1)
    for flag in ["-Wall", "-Wextra", "-Wundef", "-Wstrict-prototypes", "-Wshadow"]:
        assert flag in flags, f"C warning flag {flag} missing"

def test_rules_and_includes_exist(make_text):
    # Ensure critical include lines exist
    must_include = [
        r'^\s*include\s+\$\(CHIBIOS\)/os/common/ports/ARMCMx/compilers/GCC/mk/startup_stm32f4xx\.mk\s*$',
        r'^\s*include\s+\$\(CHIBIOS\)/os/hal/hal\.mk\s*$',
        r'^\s*include\s+\$\(CHIBIOS\)/os/rt/rt\.mk\s*$',
        r'^\s*RULESPATH\s*=\s*\$\(CHIBIOS\)/os/common/ports/ARMCMx/compilers/GCC\s*$',
        r'^\s*include\s+\$\(RULESPATH\)/rules\.mk\s*$',
        r'^\s*include\s+arm_build_tools\.mk\s*$',
    ]
    for pattern in must_include:
        assert re.search(pattern, make_text, re.M), f"Missing include/rules: {pattern}"

def test_bin_rule_gap_fill(make_text):
    # The .bin generation line should include --gap-fill 0xFF
    assert re.search(r'(?m)^build/\$\(PROJECT\)\.bin:\s*build/\$\(PROJECT\)\.elf\s*$', make_text), \
        "Missing .bin target dependency on .elf"
    assert re.search(r'(?m)^\s*\$\(BIN\)\s+build/\$\(PROJECT\)\.elf\s+build/\$\(PROJECT\)\.bin\s+--gap-fill\s+0xFF\s*$', make_text), \
        "Objcopy line should use --gap-fill 0xFF"

def test_toolchain_error_guard(make_text):
    # Verify nested ifeq with $(wildcard $(TOOLCHAIN_DIR)/*) and error
    assert re.search(r"""(?ms)^\s*ifeq\s*\(\$\(wildcard\s+\$\(TOOLCHAIN_DIR\)/\*\),\)\s*\n\s*ifeq\s*\(\$\(filter\s+\$\(MAKECMDGOALS\),arm_tools\s+arm_tools_version\s+arm_tools_clean\s+distclean\),\)\s*\n\s*\$\(error\s+"No toolchain found in \$\(TOOLCHAIN_DIR\)\. Please run 'make arm_tools' first\."\)\s*\n\s*endif\s*\n\s*endif""", make_text), \
        "The TOOLCHAIN_DIR error guard block is missing or malformed"

def test_upload_targets_openocd(make_text):
    assert re.search(r'(?ms)^\s*upload:\s*build/\$\(PROJECT\)\.bin\s*\n\s*openocd\s+-f\s+board/stm32f4discovery\.cfg\b.*program\s+build/\$\(PROJECT\)\.elf\s+verify\s+reset\s+exit"', make_text), \
        "upload target should program via stm32f4discovery.cfg"
    assert re.search(r'(?ms)^\s*upload_only:\s*\n\s*openocd\s+-f\s+board/stm32f4discovery\.cfg\b.*program\s+build/\$\(PROJECT\)\.elf\s+verify\s+reset\s+exit"', make_text), \
        "upload_only target should program via stm32f4discovery.cfg"
    assert re.search(r'(?ms)^\s*upload-olimex:\s*build/\$\(PROJECT\)\.bin\s*\n\s*openocd\s+-f\s+interface/ftdi/olimex-arm-usb-tiny-h\.cfg\b.*-f\s+interface/ftdi/olimex-arm-jtag-swd\.cfg\b.*program\s+build/\$\(PROJECT\)\.elf\s+verify\s+reset', make_text), \
        "upload-olimex target should program via FTDI configs"

def test_misc_targets_exist(make_text):
    for tgt in ["distclean: clean", "debug-start:", "size: build/$(PROJECT).elf"]:
        assert re.search(rf'^\s*{re.escape(tgt)}\s*$', make_text, re.M), f"Missing target line: {tgt}"
    # size command should use $(SZ) $<
    assert re.search(r'(?m)^\s*\@\$\(SZ\)\s*\$<\s*$', make_text), "size target should print with $(SZ) $<"

def test_linker_script_defined(make_text):
    assert re.search(r'^\s*LDSCRIPT\s*=\s*ld_eeprom_emu\.ld\s*$', make_text, re.M), "LDSCRIPT should be ld_eeprom_emu.ld"

def test_thumb_flags(make_text):
    assert re.search(r'^\s*TOPT\s*=\s*-mthumb\s+-DTHUMB\s*$', make_text, re.M), "TOPT must include -mthumb -DTHUMB"

def test_user_libs_and_defs(make_text):
    assert re.search(r'^\s*ULIBS\s*=\s*-lm\s*$', make_text, re.M), "ULIBS should include -lm"
    assert re.search(r'^\s*UDEFS\s*=\s*$', make_text, re.M), "UDEFS expected to be empty by default"

def test_compiler_tools_prefix(make_text):
    # Ensure toolchain tools variables are defined with arm-none-eabi-
    assert re.search(r'^\s*TRGT\s*=\s*arm-none-eabi-\s*$', make_text, re.M), "TRGT should be arm-none-eabi-"
    for var in ["CC", "CPPC", "LD", "CP", "AS", "AR", "OD", "SZ"]:
        assert re.search(rf'^\s*{var}\s*=\s*\$\(TRGT\)', make_text, re.M), f"{var} should be derived from TRGT"