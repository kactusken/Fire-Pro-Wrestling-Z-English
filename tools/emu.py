#!/usr/bin/env python3
"""Headless PlayStation 2 runner: the PCSX2 libretro core (LRPS2) driven from Python.

  emu.py run <image> [--out DIR] [--states DIR] [--frames N] [--state-in F] [--state-out F]
             [--shot PNG] [--bios FILE] [--card MCD] [--file STEPS.txt] [STEP...]
  emu.py setup                 where the core and the BIOS go, and whether they are there

<image> is the .iso, or the .cue of a CD game's .bin. No window, no compiler: ctypes loads the
core, runs frames, presses buttons, saves screenshots and savestates, and reads and writes main
RAM. The core draws with OpenGL, so the runner makes an off-screen OpenGL context itself (EGL on
Mesa's surfaceless platform - no display needed; the libEGL and Mesa drivers of any desktop Linux
or WSL, where Mesa reaches the GPU through /dev/dxg) and reads the frame back from its own
framebuffer when a screenshot is asked for. About 300-600 frames a second once the disc is read.

Files (outside every git repository - the BIOS is never committed):
  ~/.local/share/kit-emu/cores/pcsx2_libretro.so    from the libretro buildbot
      (https://buildbot.libretro.com/nightly/linux/x86_64/latest/pcsx2_libretro.so.zip)
  ~/.local/share/kit-emu/system/pcsx2/bios/         the owner's BIOS dumps (required: the core has
      no HLE BIOS); `emu.py setup` links system/ps2/ there if the dumps were put in that folder.
      The runner picks the dump whose region matches the disc (SLPM/SLPS/SCPS.. Japan, SLUS/SCUS
      America, SLES/SCES Europe; a ROMVER of 0100J.. is a Japanese BIOS) - --bios to choose.

Memory cards: every run starts with fresh, empty cards (the core formats them), so a game that
autoloads finds nothing and runs on the original and on a build behave alike. --card MCD (a
PCSX2 .ps2 card file) puts a copy of that card in slot 1 instead - a save made in PCSX2 to start
from. The run's cards live in a temporary folder and are gone afterwards; use savestates to keep
a place.

Steps - one per argument, or one per line in --file (# comments); the same words as the Saturn,
Dreamcast and SNES runners, so testing/drive.py step files work on all of them:
  wait N                      run N frames
  press BUTTONS [N] [xK]      hold buttons (CROSS CIRCLE SQUARE TRIANGLE START SELECT UP DOWN
                              LEFT RIGHT L1 R1 L2 R2 L3 R3, joined by +) for N frames (default 4),
                              then release for 12; xK: K times
  mash BUTTONS FRAMES [EVERY] press for 4 frames every EVERY (default 12), for FRAMES frames
  shot NAME                   screenshot -> OUT/NAME.png (a NAME ending .png is a path)
  save NAME / load NAME       savestate -> / <- STATES/NAME.state (a NAME ending .state is a path)
  peek ADDR [LEN]             print LEN main-RAM bytes (default 1), also -> OUT/peek.txt
  poke ADDR BYTE[,BYTE...]    write bytes into main RAM              poke 0031A2B0 1,0,0,0
  dump REGION START LEN NAME  memory -> OUT/NAME.bin; REGION ram (32 MB from 00000000), START an
                              offset in it (the core gives no GS video memory)
  until ADDR BYTE [LIMIT]     run until the RAM byte at ADDR is BYTE (at most LIMIT frames,
                              default 600)
Addresses are hex (0031A2B0, 0x0031A2B0, $0031A2B0): the EE's own addresses, as in the ELF and
in a disassembly - main RAM is 00000000-01FFFFFF, also through its mirrors 20/30/80/A0000000.
Byte values, LEN and frame counts are DECIMAL unless written $xx or 0x... Memory is little-endian.

As a library: Ps2(image) -> .run(frames), .press(...), .screenshot(path), .read(addr, n),
.write(addr, bytes), .memory(region), .save_state(), .load_state(bytes), .state_poke(state, addr,
bytes) (a copy of a savestate with RAM changed, made through the running core); run_steps(emu,
steps, out, states) runs steps.
"""
import argparse
import ctypes as C
import os
import re
import shutil
import struct
import sys
import tempfile
import zlib
from pathlib import Path

HOME = Path(os.environ.get('KIT_EMU', Path.home() / '.local/share/kit-emu'))
CORE = HOME / 'cores' / 'pcsx2_libretro.so'
SYSTEM = HOME / 'system'
SAVES = HOME / 'saves'
BIOS_DIR = SYSTEM / 'pcsx2' / 'bios'
RAM_SIZE = 32 << 20

# PS2 pad button -> libretro joypad id (the RetroPad by position: B is Cross, A Circle, Y Square,
# X Triangle); L2/R2 are also answered as analog triggers
BUTTONS = {'CROSS': 0, 'SQUARE': 1, 'SELECT': 2, 'START': 3, 'UP': 4, 'DOWN': 5, 'LEFT': 6, 'RIGHT': 7,
           'CIRCLE': 8, 'TRIANGLE': 9, 'L1': 10, 'R1': 11, 'L2': 12, 'R2': 13, 'L3': 14, 'R3': 15}
# the disc serial's prefix -> the BIOS region letter in ROMVER
REGIONS = {'SLPM': 'J', 'SLPS': 'J', 'SCPS': 'J', 'SCAJ': 'J', 'SLAJ': 'J', 'PAPX': 'J', 'SLKA': 'J',
           'SCKA': 'J', 'SLUS': 'A', 'SCUS': 'A', 'SLES': 'E', 'SCES': 'E', 'SCED': 'E'}

ENV_CB = C.CFUNCTYPE(C.c_bool, C.c_uint, C.c_void_p)
VIDEO_CB = C.CFUNCTYPE(None, C.c_void_p, C.c_uint, C.c_uint, C.c_size_t)
AUDIO_CB = C.CFUNCTYPE(None, C.c_int16, C.c_int16)
AUDIO_BATCH_CB = C.CFUNCTYPE(C.c_size_t, C.c_void_p, C.c_size_t)
POLL_CB = C.CFUNCTYPE(None)
INPUT_CB = C.CFUNCTYPE(C.c_int16, C.c_uint, C.c_uint, C.c_uint, C.c_uint)
FB_CB = C.CFUNCTYPE(C.c_size_t)
PROC_CB = C.CFUNCTYPE(C.c_void_p, C.c_char_p)
LOG_CB = C.CFUNCTYPE(None, C.c_int, C.c_char_p)          # retro_log_printf_t (the format only)
HW_FRAME = 0xFFFFFFFFFFFFFFFF if C.sizeof(C.c_void_p) == 8 else 0xFFFFFFFF   # RETRO_HW_FRAME_BUFFER_VALID


class GameInfo(C.Structure):
    _fields_ = [('path', C.c_char_p), ('data', C.c_void_p), ('size', C.c_size_t), ('meta', C.c_char_p)]


class Variable(C.Structure):
    _fields_ = [('key', C.c_char_p), ('value', C.c_char_p)]


class HwRender(C.Structure):     # struct retro_hw_render_callback
    _fields_ = [('context_type', C.c_uint), ('context_reset', C.c_void_p), ('get_current_framebuffer', C.c_void_p),
                ('get_proc_address', C.c_void_p), ('depth', C.c_bool), ('stencil', C.c_bool),
                ('bottom_left_origin', C.c_bool), ('version_major', C.c_uint), ('version_minor', C.c_uint),
                ('cache_context', C.c_bool), ('context_destroy', C.c_void_p), ('debug_context', C.c_bool)]


class Geometry(C.Structure):
    _fields_ = [('base_width', C.c_uint), ('base_height', C.c_uint), ('max_width', C.c_uint),
                ('max_height', C.c_uint), ('aspect', C.c_float)]


class AvInfo(C.Structure):
    _fields_ = [('geometry', Geometry), ('fps', C.c_double), ('sample_rate', C.c_double)]


OPTIONS = {b'pcsx2_renderer': b'OpenGL', b'pcsx2_fastboot': b'enabled', b'pcsx2_fastcdvd': b'disabled',
           b'pcsx2_upscale_multiplier': b'1x (Native)', b'pcsx2_shared_memory_cards': b'enabled',
           b'pcsx2_enable_cheats': b'disabled', b'pcsx2_widescreen_hint': b'disabled',
           b'pcsx2_uncapped_framerate_hint': b'disabled', b'pcsx2_game_enhancements_hint': b'disabled'}


class Gl:
    """An off-screen OpenGL context (EGL, Mesa surfaceless platform) and a framebuffer for the core."""
    EGL_NONE = 0x3038

    def __init__(self, core_profile, major, minor):
        egl = self.egl = C.CDLL('libEGL.so.1')
        egl.eglGetProcAddress.restype = C.c_void_p
        egl.eglGetProcAddress.argtypes = [C.c_char_p]
        for name, res in (('eglGetDisplay', C.c_void_p), ('eglCreateContext', C.c_void_p),
                          ('eglInitialize', C.c_bool), ('eglBindAPI', C.c_bool), ('eglChooseConfig', C.c_bool),
                          ('eglMakeCurrent', C.c_bool), ('eglGetError', C.c_int)):
            getattr(egl, name).restype = res
        egl.eglCreateContext.argtypes = [C.c_void_p, C.c_void_p, C.c_void_p, C.POINTER(C.c_int)]
        egl.eglMakeCurrent.argtypes = [C.c_void_p, C.c_void_p, C.c_void_p, C.c_void_p]
        egl.eglChooseConfig.argtypes = [C.c_void_p, C.POINTER(C.c_int), C.POINTER(C.c_void_p), C.c_int,
                                        C.POINTER(C.c_int)]
        egl.eglInitialize.argtypes = [C.c_void_p, C.c_void_p, C.c_void_p]
        get_display = C.CFUNCTYPE(C.c_void_p, C.c_uint, C.c_void_p, C.c_void_p)(
            egl.eglGetProcAddress(b'eglGetPlatformDisplayEXT'))
        self.dpy = get_display(0x31DD, None, None)            # EGL_PLATFORM_SURFACELESS_MESA
        if not self.dpy or not egl.eglInitialize(self.dpy, None, None):
            raise SystemExit(f'EGL: no surfaceless display (error {egl.eglGetError():#x}) - needs Mesa\'s libEGL')
        egl.eglBindAPI(0x30A2)                                # EGL_OPENGL_API
        attrs = (C.c_int * 13)(0x3033, 0x1, 0x3040, 0x8, 0x3024, 8, 0x3023, 8, 0x3022, 8, 0x3021, 8, self.EGL_NONE)
        cfg, n = C.c_void_p(), C.c_int()
        if not egl.eglChooseConfig(self.dpy, attrs, C.byref(cfg), 1, C.byref(n)) or not n.value:
            raise SystemExit('EGL: no OpenGL config')
        ctx_attrs = (C.c_int * 7)(0x3098, major, 0x30FB, minor, 0x30FD, 1 if core_profile else 2, self.EGL_NONE)
        self.ctx = egl.eglCreateContext(self.dpy, cfg, None, ctx_attrs)
        if not self.ctx or not egl.eglMakeCurrent(self.dpy, None, None, self.ctx):
            raise SystemExit(f'EGL: no OpenGL {major}.{minor} context (error {egl.eglGetError():#x})')
        self.fbo = 0
        self.size = (0, 0)

    def proc(self, name):
        return self.egl.eglGetProcAddress(name)

    def fn(self, name, res, *args):
        return C.CFUNCTYPE(res, *args)(self.proc(name.encode()))

    def framebuffer(self, w, h):
        """A framebuffer with RGBA8 colour and depth/stencil at w x h; its name."""
        gen = self.fn('glGenFramebuffers', None, C.c_int, C.POINTER(C.c_uint))
        bind = self.fn('glBindFramebuffer', None, C.c_uint, C.c_uint)
        genrb = self.fn('glGenRenderbuffers', None, C.c_int, C.POINTER(C.c_uint))
        bindrb = self.fn('glBindRenderbuffer', None, C.c_uint, C.c_uint)
        storage = self.fn('glRenderbufferStorage', None, C.c_uint, C.c_uint, C.c_int, C.c_int)
        attach = self.fn('glFramebufferRenderbuffer', None, C.c_uint, C.c_uint, C.c_uint, C.c_uint)
        status = self.fn('glCheckFramebufferStatus', C.c_uint, C.c_uint)
        fbo, rb = C.c_uint(), (C.c_uint * 2)()
        gen(1, C.byref(fbo))
        bind(0x8D40, fbo.value)
        genrb(2, rb)
        for buf, fmt, point in ((rb[0], 0x8058, 0x8CE0), (rb[1], 0x88F0, 0x821A)):   # RGBA8 / DEPTH24_STENCIL8
            bindrb(0x8D41, buf)
            storage(0x8D41, fmt, w, h)
            attach(0x8D40, point, 0x8D41, buf)
        if status(0x8D40) != 0x8CD5:
            raise SystemExit('OpenGL: framebuffer incomplete')
        self.fbo, self.size = fbo.value, (w, h)
        return self.fbo

    def read(self, w, h):
        """RGBA rows of the framebuffer, top row first."""
        bind = self.fn('glBindFramebuffer', None, C.c_uint, C.c_uint)
        pixel_store = self.fn('glPixelStorei', None, C.c_uint, C.c_int)
        read = self.fn('glReadPixels', None, C.c_int, C.c_int, C.c_int, C.c_int, C.c_uint, C.c_uint, C.c_void_p)
        buf = C.create_string_buffer(w * h * 4)
        bind(0x8CA8, self.fbo)                                # GL_READ_FRAMEBUFFER
        pixel_store(0x0D05, 1)                                # GL_PACK_ALIGNMENT
        read(0, 0, w, h, 0x1908, 0x1401, buf)                 # GL_RGBA, GL_UNSIGNED_BYTE
        raw = buf.raw
        return [raw[(h - 1 - y) * w * 4:(h - y) * w * 4] for y in range(h)]


def bios_region(path):
    """The region letter of a PS2 BIOS dump (J, A, E, H, C, T) from its ROMVER, or None."""
    m = re.search(rb'\d{4}([JAEHCT])[CDTP]\d{8}', Path(path).read_bytes()[:4 << 20])
    return m.group(1).decode() if m else None


def disc_serial(image):
    """The boot file's serial (SLPM_623.42) from SYSTEM.CNF, or None."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import disc
        image = Path(image)
        if image.suffix.lower() == '.cue':
            m = re.search(r'FILE\s+"([^"]+)"', image.read_text(errors='replace'))
            image = image.parent / m.group(1)
        d = disc.Disc(str(image))
        try:
            cnf = d.read_file(d.find('SYSTEM.CNF')).decode('latin-1')
        finally:
            d.close()
        m = re.search(r'BOOT2\s*=\s*cdrom0:\\?([^;\r\n]+)', cnf)
        return m.group(1).strip() if m else None
    except Exception:
        return None


def bioses():
    """BIOS dumps in BIOS_DIR: {file name: region letter} (the core lists the same files)."""
    if not BIOS_DIR.is_dir():
        return {}
    return {f.name: bios_region(f) for f in sorted(BIOS_DIR.iterdir())
            if f.is_file() and f.stat().st_size in (4 << 20, 8 << 20) and bios_region(f)}


def pick_bios(image, choice=None):
    """The BIOS file name for this disc: `choice`, else the dump of the disc's region, else the
    first dump found."""
    found = bioses()
    if not found:
        raise SystemExit(f'no PS2 BIOS in {BIOS_DIR} - run `emu.py setup`')
    if choice:
        name = Path(choice).name
        if name not in found:
            raise SystemExit(f'BIOS {name} is not in {BIOS_DIR} (there: {", ".join(found)})')
        return name
    serial = disc_serial(image) or ''
    want = REGIONS.get(serial[:4].upper())
    return next((n for n, r in found.items() if r == want), next(iter(found)))


class Ps2:
    def __init__(self, image, core=CORE, options=None, bios=None, card=None):
        if not Path(core).exists():
            raise SystemExit(f'no core at {core} - run `emu.py setup` for where to get it')
        SAVES.mkdir(parents=True, exist_ok=True)
        # the core's system folder, made for this run: the BIOS and caches linked in, fresh memory
        # cards (or a copy of `card`) that nothing else sees
        self._tmp = tempfile.TemporaryDirectory(prefix='kit-ps2-')
        sysdir = Path(self._tmp.name)
        (sysdir / 'pcsx2' / 'memcards').mkdir(parents=True)
        os.symlink(BIOS_DIR.resolve(), sysdir / 'pcsx2' / 'bios')
        for keep in ('cache', 'textures'):
            (SYSTEM / 'pcsx2' / keep).mkdir(parents=True, exist_ok=True)
            os.symlink(SYSTEM / 'pcsx2' / keep, sysdir / 'pcsx2' / keep)
        if card:
            shutil.copyfile(card, sysdir / 'pcsx2' / 'memcards' / 'Mcd001.ps2')
        self.card_dir = sysdir / 'pcsx2' / 'memcards'
        self.lib = C.CDLL(str(core))
        self.bios = pick_bios(image, bios)
        self.opts = {**OPTIONS, b'pcsx2_bios': self.bios.encode(), **(options or {})}
        self.held = set()
        self._ram = None
        self.frame = None            # software frames: (bytes, width, height, pitch); hardware: (None, w, h, 0)
        self.fmt = 0
        self.gl = None
        self.hw = None
        self._keep = []
        self._sysdir = C.c_char_p(str(sysdir).encode())
        self._savedir = C.c_char_p(str(SAVES).encode())
        self._optvals = {k: C.c_char_p(v) for k, v in self.opts.items()}
        self._fb_cb, self._proc_cb = FB_CB(lambda: self.gl.fbo if self.gl else 0), PROC_CB(self._proc)
        self.log = []                # the core's log lines (format strings: ctypes can't take varargs)
        self._log_cb = LOG_CB(lambda level, fmt: self.log.append(fmt.decode('latin-1', 'replace').rstrip())
                              if level >= 2 else None)
        cbs = [ENV_CB(self._env), VIDEO_CB(self._video), AUDIO_CB(lambda l, r: None),
               AUDIO_BATCH_CB(lambda d, n: n), POLL_CB(lambda: None), INPUT_CB(self._input)]
        self._keep += cbs
        self.lib.retro_set_environment(cbs[0])
        self.lib.retro_set_video_refresh(cbs[1])
        self.lib.retro_set_audio_sample(cbs[2])
        self.lib.retro_set_audio_sample_batch(cbs[3])
        self.lib.retro_set_input_poll(cbs[4])
        self.lib.retro_set_input_state(cbs[5])
        self.lib.retro_init()
        info = GameInfo(str(image).encode(), None, 0, None)
        self.lib.retro_load_game.restype = C.c_bool
        if not self.lib.retro_load_game(C.byref(info)):
            raise SystemExit(f'the core could not load {image} (BIOS {self.bios})'
                             + ''.join(f'\n  {line}' for line in self.log[-5:]))
        if self.hw is None:
            raise SystemExit('the core asked for no OpenGL context (this runner only does OpenGL)')
        self.lib.retro_set_controller_port_device(0, 1)   # a pad in port 1
        av = AvInfo()
        self.lib.retro_get_system_av_info(C.byref(av))
        self.gl.framebuffer(max(av.geometry.max_width, 640), max(av.geometry.max_height, 512))
        if self.hw.context_reset:
            C.CFUNCTYPE(None)(self.hw.context_reset)()
        self.lib.retro_serialize_size.restype = C.c_size_t
        self.lib.retro_serialize.restype = C.c_bool
        self.lib.retro_unserialize.restype = C.c_bool

    # ---- callbacks
    def _proc(self, name):
        return self.gl.proc(name) if self.gl else None

    def _env(self, cmd, data):
        cmd &= 0xFFFF                                  # drop RETRO_ENVIRONMENT_EXPERIMENTAL
        if cmd == 9 or cmd == 31:                      # GET_SYSTEM_DIRECTORY / GET_SAVE_DIRECTORY
            C.cast(data, C.POINTER(C.c_char_p))[0] = (self._sysdir if cmd == 9 else self._savedir).value
            return True
        if cmd == 10:                                  # SET_PIXEL_FORMAT
            self.fmt = C.cast(data, C.POINTER(C.c_int))[0]
            return True
        if cmd == 14:                                  # SET_HW_RENDER: OpenGL (compatibility or core) only
            hw = C.cast(data, C.POINTER(HwRender))[0]
            if hw.context_type not in (1, 3):
                return False
            core = hw.context_type == 3
            self.gl = self.gl or Gl(core, hw.version_major if core else 2, hw.version_minor if core else 1)
            hw.get_current_framebuffer = C.cast(self._fb_cb, C.c_void_p).value
            hw.get_proc_address = C.cast(self._proc_cb, C.c_void_p).value
            C.cast(data, C.POINTER(HwRender))[0] = hw
            self.hw = hw
            return True
        if cmd == 27:                                  # GET_LOG_INTERFACE
            C.cast(data, C.POINTER(C.c_void_p))[0] = C.cast(self._log_cb, C.c_void_p).value
            return True
        if cmd == 56:                                  # GET_PREFERRED_HW_RENDER: OpenGL core
            C.cast(data, C.POINTER(C.c_uint))[0] = 3
            return True
        if cmd == 15:                                  # GET_VARIABLE
            v = C.cast(data, C.POINTER(Variable))[0]
            val = self._optvals.get(v.key)
            if val is None:
                return False
            C.cast(data, C.POINTER(Variable))[0].value = val.value
            return True
        if cmd == 3:                                   # GET_CAN_DUPE
            C.cast(data, C.POINTER(C.c_bool))[0] = True
            return True
        if cmd == 17:                                  # GET_VARIABLE_UPDATE
            C.cast(data, C.POINTER(C.c_bool))[0] = False
            return True
        if cmd == 52:                                  # GET_CORE_OPTIONS_VERSION
            C.cast(data, C.POINTER(C.c_uint))[0] = 0
            return True
        return False

    def _video(self, data, w, h, pitch):
        if data == HW_FRAME and self.gl:
            self.frame = (None, w, h, 0)
        elif data:
            self.frame = (C.string_at(data, pitch * h), w, h, pitch)

    def _input(self, port, device, index, button):
        if port != 0:
            return 0
        if device == 1:                                # RETRO_DEVICE_JOYPAD
            if button == 256:                          # RETRO_DEVICE_ID_JOYPAD_MASK: LRPS2 reads the pad this way
                return sum(1 << b for b in self.held)
            return 1 if button in self.held else 0
        if device == 5 and index == 2:                 # button pressure (the DualShock 2's analog buttons)
            return 0x7FFF if button in self.held else 0
        return 0

    # ---- control
    def run(self, frames=1):
        for _ in range(frames):
            self.lib.retro_run()
        self.frames_run = getattr(self, 'frames_run', 0) + frames

    def press(self, buttons, frames=4, release=4):
        try:
            self.held = {BUTTONS[b.upper()] for b in buttons.split('+') if b}
        except KeyError as e:
            raise SystemExit(f'no PS2 button {e} ({" ".join(BUTTONS)})')
        self.run(frames)
        self.held = set()
        self.run(release)

    def save_state(self):
        n = self.lib.retro_serialize_size()
        buf = C.create_string_buffer(n)
        if not self.lib.retro_serialize(buf, C.c_size_t(n)):
            raise SystemExit('savestate failed')
        return buf.raw

    def load_state(self, data):
        buf = C.create_string_buffer(data, len(data))
        if not self.lib.retro_unserialize(buf, C.c_size_t(len(data))):
            raise SystemExit('loading the savestate failed')

    def state_poke(self, data, addr, value):
        """A copy of savestate `data` with bytes `value` written at main-RAM address `addr` - made
        by the running core (load, write, save), which goes back to where it was afterwards."""
        here = self.save_state()
        self.load_state(data)
        self.write(addr, value)
        out = self.save_state()
        self.load_state(here)
        return out

    def rgb(self):
        """The current frame as (width, height, rows of (r, g, b))."""
        if not self.frame:
            raise SystemExit('no frame yet - run some frames first')
        data, w, h, pitch = self.frame
        if data is None:
            return w, h, [[(r[4 * x], r[4 * x + 1], r[4 * x + 2]) for x in range(w)] for r in self.gl.read(w, h)]
        rows = []
        for y in range(h):
            line = data[y * pitch:y * pitch + pitch]
            if self.fmt == 1:
                rows.append([(line[4 * x + 2], line[4 * x + 1], line[4 * x]) for x in range(w)])
            else:
                px = struct.unpack_from(f'<{w}H', line)
                if self.fmt == 2:
                    rows.append([((p >> 11) << 3, ((p >> 5) & 63) << 2, (p & 31) << 3) for p in px])
                else:
                    rows.append([(((p >> 10) & 31) << 3, ((p >> 5) & 31) << 3, (p & 31) << 3) for p in px])
        return w, h, rows

    def screenshot(self, path):
        w, h, rows = self.rgb()
        raw = b''.join(b'\0' + bytes(c for px in r for c in px) for r in rows)

        def chunk(t, d):
            return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d))
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
                               + chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b''))
        return w, h

    def _region(self, kind):
        self.lib.retro_get_memory_data.restype = C.c_void_p
        self.lib.retro_get_memory_size.restype = C.c_size_t
        p, n = self.lib.retro_get_memory_data(kind), self.lib.retro_get_memory_size(kind)
        return (C.c_ubyte * n).from_address(p) if p and n else None

    def ram(self):
        """Main RAM as the core keeps it (live, writable, 32 MB, little-endian; index = address)."""
        if self._ram is None:
            self._ram = self._region(2)                # RETRO_MEMORY_SYSTEM_RAM
            if self._ram is None or len(self._ram) < RAM_SIZE:
                raise SystemExit('the core gives no main RAM')
        return self._ram

    def read(self, addr, n=1):
        o = ram_offset(addr, n)
        return bytes(self.ram()[o:o + n])

    def write(self, addr, data):
        o, r = ram_offset(addr, len(data)), self.ram()
        for k, b in enumerate(data):
            r[o + k] = b

    def memory(self, region):
        """ram: main RAM (32 MB from 00000000)."""
        if region == 'ram':
            return bytes(self.ram())[:RAM_SIZE]
        raise SystemExit(f'unknown memory region {region!r} (ram; the core gives no GS video memory)')


def ram_offset(addr, n=1):
    """Index of EE address `addr` in main RAM (00000000-01FFFFFF and its 20/30/80/A0 mirrors)."""
    if addr >> 28 not in (0x0, 0x2, 0x3, 0x8, 0xA) or addr & 0x0E000000:
        raise SystemExit(f'{addr:08X}: not main RAM (00000000-01FFFFFF, or its 20/30/80/A0000000 mirrors)')
    o = addr & 0x01FFFFFF
    if o + n > RAM_SIZE:
        raise SystemExit(f'{addr:08X}+{n}: runs past the end of main RAM')
    return o


def num(s):
    """A decimal number, or hex written $xx / 0x.."""
    return int(s[1:], 16) if s.startswith('$') else int(s, 0)


def addr(s):
    """A hex address: 0031A2B0, 0x0031A2B0, $0031A2B0."""
    return int(s.lstrip('$').removeprefix('0x').removeprefix('0X'), 16)


def clean_steps(steps):
    return [s.split('#')[0].strip() for s in steps if s.split('#')[0].strip()]


def run_steps(emu, steps, out, states=None, log=print):
    """Run steps (see the module help) on a PS2; screenshots, dumps and peek.txt go to `out`,
    savestates to `states` (default out/states)."""
    out = Path(out)
    states = Path(states) if states else out / 'states'
    for line in clean_steps(steps):
        cmd, *a = line.split()
        cmd = cmd.lower()
        try:
            if cmd == 'wait':
                emu.run(num(a[0]))
            elif cmd == 'press':
                k = num(a.pop()[1:]) if a[-1][:1] in 'xX' and a[-1][1:].isdigit() else 1
                for _ in range(k):
                    emu.press(a[0], num(a[1]) if len(a) > 1 else 4, 12)
            elif cmd == 'mash':
                frames, every = num(a[1]), num(a[2]) if len(a) > 2 else 12
                for _ in range(max(1, frames // every)):
                    emu.press(a[0], 4, max(0, every - 4))
            elif cmd == 'shot':
                f = Path(a[0]) if a[0].endswith('.png') else out / f'{a[0]}.png'
                emu.screenshot(f)
            elif cmd in ('save', 'load'):
                f = Path(a[0]) if a[0].endswith('.state') else states / f'{a[0]}.state'
                if cmd == 'save':
                    f.parent.mkdir(parents=True, exist_ok=True)
                    f.write_bytes(emu.save_state())
                else:
                    if not getattr(emu, 'frames_run', 0):
                        emu.run(60)     # the core crashes (SIGSEGV) unserializing before any frame ran
                    emu.load_state(f.read_bytes())
                    emu.run(2)
            elif cmd == 'peek':
                n = num(a[1]) if len(a) > 1 else 1
                text = f'peek {addr(a[0]):08X}: {emu.read(addr(a[0]), n).hex(" ")}'
                log(text)
                out.mkdir(parents=True, exist_ok=True)
                with open(out / 'peek.txt', 'a') as f:
                    f.write(text + '\n')
            elif cmd == 'poke':
                emu.write(addr(a[0]), bytes(num(v) for v in ','.join(a[1:]).split(',') if v))
            elif cmd == 'dump':
                m, start, n = emu.memory(a[0].lower()), addr(a[1]), num(a[2])
                out.mkdir(parents=True, exist_ok=True)
                (out / f'{a[3]}.bin').write_bytes(m[start:start + n])
            elif cmd == 'until':
                at, want, limit = addr(a[0]), num(a[1]), num(a[2]) if len(a) > 2 else 600
                while emu.read(at)[0] != want and limit > 0:
                    emu.run(1)
                    limit -= 1
                if limit <= 0:
                    log(f'until {at:08X} {want}: not reached')
            else:
                raise SystemExit(f'unknown step {line!r} (see emu.py --help)')
        except (IndexError, ValueError) as e:
            raise SystemExit(f'step {line!r}: {e} (see emu.py --help)')


def setup():
    print(('ok      ' if CORE.exists() else 'MISSING ') + str(CORE))
    legacy = SYSTEM / 'ps2'
    if not BIOS_DIR.exists() and legacy.is_dir():
        BIOS_DIR.parent.mkdir(parents=True, exist_ok=True)
        os.symlink('../ps2', BIOS_DIR)
        print(f'linked  {BIOS_DIR} -> {legacy}')
    found = bioses()
    for name, region in found.items():
        print(f'ok      {BIOS_DIR / name} (region {region})')
    if not found:
        print(f'MISSING a PS2 BIOS dump in {BIOS_DIR} (required)')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('run')
    p.add_argument('image')
    p.add_argument('steps', nargs='*')
    p.add_argument('--file', '--script', dest='file')
    p.add_argument('--out', default='.')
    p.add_argument('--states')
    p.add_argument('--frames', type=int, default=0)
    p.add_argument('--shot')
    p.add_argument('--state-in')
    p.add_argument('--state-out')
    p.add_argument('--bios')
    p.add_argument('--card')
    sub.add_parser('setup')
    a, rest = ap.parse_known_args(argv)       # steps may come after the options
    if any(r.startswith('-') for r in rest):
        ap.error(f'unrecognized arguments: {" ".join(rest)}')
    if a.cmd == 'setup':
        return setup()
    emu = Ps2(a.image, bios=a.bios, card=a.card)
    if a.state_in:
        emu.load_state(Path(a.state_in).read_bytes())
    emu.run(a.frames)
    steps = (Path(a.file).read_text().splitlines() if a.file else []) + a.steps + rest
    run_steps(emu, steps, a.out, a.states)
    if a.shot:
        print(a.shot, emu.screenshot(a.shot))
    if a.state_out:
        Path(a.state_out).write_bytes(emu.save_state())


if __name__ == '__main__':
    main()
