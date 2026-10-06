#!/usr/bin/env python3
"""The measurements inside index.html, rebuilt from their sources.

The page carries five blocks of data that nobody should edit by hand:

    STARS      the Yale Bright Star Catalogue to magnitude 5.6, eight bytes a
               star: where it is, how bright, what colour, and how far
    MAPS       fourteen maps, reduced from public-domain NASA and USGS imagery
    MOON_FIT   the orbits of nineteen moons, fitted to JPL Horizons
    NEAR       the stars within twelve light-years, and three bright ones beyond
    CRAFT      the five spacecraft that are leaving, where they were on JD0

This script fetches the sources (into a cache outside the repo), rebuilds
the five blocks and writes them back into the page between the lines that
declare them. It also checks the page's arithmetic against Horizons.

    python3 tools/solar_data.py build index.html            # fetch what is missing, rebuild, write into the page
    python3 tools/solar_data.py check index.html            # the page's own elements, against Horizons
    python3 tools/solar_data.py sheet index.html maps.png   # a contact sheet of the maps as they ship

Needs Pillow. Everything it downloads is public domain (NASA, USGS, the
Yale catalogue via CDS) or, for Horizons and SIMBAD, a free public service
(of JPL, and of the CDS in Strasbourg, which asks to be named).
The first build fetches about 700 MB: the four USGS mosaics of Jupiter's
large moons are between 115 and 197 MB each."""
import base64, gzip, io, itertools, json, math, os, random, re, struct, sys, tempfile, time, urllib.parse, urllib.request, zlib

CACHE = os.environ.get("SOLAR_CACHE") or os.path.join(tempfile.gettempdir(), "solar_data")
UA = {"User-Agent": "solar_data.py (personal project)"}
D2R = math.pi / 180
EPS = 23.43928 * D2R
AU = 149597870.7
JD0 = 2461311.5                       # 2026-09-28: the day the moons' angles are counted from

SOURCES = {
    "bsc5.dat.gz":      "https://cdsarc.cds.unistra.fr/ftp/cats/V/50/catalog.gz",
    "earth_topo.jpg":   "https://eoimages.gsfc.nasa.gov/images/imagerecords/74000/74393/world.topo.200407.3x5400x2700.jpg",
    "earth_clouds.jpg": "https://eoimages.gsfc.nasa.gov/images/imagerecords/57000/57747/cloud_combined_2048.jpg",
    "earth_night.jpg":  "https://eoimages.gsfc.nasa.gov/images/imagerecords/144000/144898/BlackMarble_2016_01deg.jpg",
    "moon.tif":         "https://svs.gsfc.nasa.gov/vis/a000000/a004700/a004720/lroc_color_poles_4k.tif",
    "milkyway_4k.exr":  "https://svs.gsfc.nasa.gov/vis/a000000/a004800/a004851/milkyway_2020_4k.exr",
    "io.tif":           "https://planetarymaps.usgs.gov/mosaic/Io_GalileoSSI-Voyager_Global_Mosaic_ClrMerge_1km.tif",
    "europa.tif":       "https://planetarymaps.usgs.gov/mosaic/Europa_Voyager_GalileoSSI_global_mosaic_500m.tif",
    "ganymede.tif":     "https://planetarymaps.usgs.gov/mosaic/Ganymede_Voyager_GalileoSSI_global_mosaic_1km.tif",
    "callisto.tif":     "https://planetarymaps.usgs.gov/mosaic/Callisto_Voyager_GalileoSSI_global_mosaic_1km.tif",
}
# held on Wikimedia Commons, each marked public domain (NASA / JPL / USGS / JHUAPL / SwRI)
COMMONS = {
    "mars_2560.jpg":    "File:Mars Viking MDIM21 ClrMosaic 1km.jpg",
    "mercury_2560.png": "File:Mercury global map 2013-05-14 bright.png",
    "jupiter_2560.jpg": "File:Jupiter Cylindrical Map - Dec 2000 PIA07782.jpg",
    "pluto_2560.jpg":   "File:Pluto color mapmosaic.jpg",
}
MOONS = {"phobos": (401, 499), "deimos": (402, 499), "io": (501, 599), "europa": (502, 599), "ganymede": (503, 599),
         "callisto": (504, 599), "enceladus": (602, 699), "tethys": (603, 699), "dione": (604, 699), "rhea": (605, 699),
         "titan": (606, 699), "iapetus": (608, 699), "miranda": (705, 799), "ariel": (701, 799), "umbriel": (702, 799),
         "titania": (703, 799), "oberon": (704, 799), "triton": (801, 899), "charon": (901, 999)}
# the five that are leaving: Horizons' number, and the day after the last world each one passed.
# From that day on nothing has pulled on it but the Sun, and its path is one curve.
CRAFT = {"voyager1": (-31, "1980-11-13"), "voyager2": (-32, "1989-08-26"), "pioneer10": (-23, "1973-12-05"),
         "pioneer11": (-24, "1979-09-02"), "newhorizons": (-98, "2015-07-15")}
# the neighbours, by the name SIMBAD knows each one by. Then, where they are
# needed: a brightness V for one that SIMBAD holds none for, and a colour B-V
# to use instead of SIMBAD's (what it holds for a brown dwarf is no colour the
# eye would see).
NEAR = {"proxima": ("NAME Proxima Centauri",), "alfcen": ("* alf Cen",), "barnard": ("NAME Barnard's star",),
        "luhman16": ("NAME Luhman 16", None, 2.2), "wise0855": ("WISEA J085510.74-071442.5", 25.0, 2.2), "wolf359": ("Wolf 359",),
        "lalande21185": ("HD 95735",), "sirius": ("* alf CMa",), "luyten7268": ("G 272-61",), "ross154": ("Ross 154",),
        "ross248": ("Ross 248", 12.29, 1.9), "epseri": ("* eps Eri",), "lacaille9352": ("HD 217987",), "ross128": ("Ross 128",),
        "ezaqr": ("V* EZ Aqr",), "cyg61": ("* 61 Cyg A",), "procyon": ("* alf CMi",), "struve2398": ("HD 173739",),
        "groombridge34": ("HD 1326",), "dxcnc": ("G 51-15", 14.81, 2.06), "epsind": ("* eps Ind",), "tauceti": ("* tau Cet",),
        "gj1061": ("GJ 1061",), "altair": ("* alf Aql",), "vega": ("* alf Lyr",), "fomalhaut": ("* alf PsA",)}
LY_PC = 3.2615637769                  # light-years in a parsec
PLANETS = {"mercury": 199, "venus": 299, "earth": 399, "mars": 499, "jupiter": 599, "saturn": 699, "uranus": 799,
           "neptune": 899, "pluto": 999}


# ---- fetching ------------------------------------------------------------
def get(url, tries=3):
    for k in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=900).read()
        except Exception as e:
            if k == tries - 1: raise
            time.sleep(2)

def cached(name, make):
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, name)
    if not os.path.exists(p) or os.path.getsize(p) < 500:
        print("  fetching", name)
        open(p, "wb").write(make())
    return p

def source(name):
    if name in SOURCES:
        return cached(name, lambda: get(SOURCES[name]))
    def commons():
        q = urllib.parse.urlencode({"action": "query", "prop": "imageinfo", "iiprop": "url", "iiurlwidth": 2560,
                                    "format": "json", "titles": COMMONS[name]})
        d = json.loads(get("https://commons.wikimedia.org/w/api.php?" + q))
        return get(next(iter(d["query"]["pages"].values()))["imageinfo"][0]["thumburl"])
    return cached(name, commons)

def horizons(name, **p):
    def ask():
        q = {"format": "text", "OBJ_DATA": "'NO'", "MAKE_EPHEM": "'YES'", "REF_PLANE": "'ECLIPTIC'", "REF_SYSTEM": "'ICRF'",
             "CSV_FORMAT": "'YES'"}
        q.update({k: "'%s'" % v for k, v in p.items()})
        time.sleep(0.4)
        return get("https://ssd.jpl.nasa.gov/api/horizons.api?" + urllib.parse.urlencode(q))
    t = open(cached("hz_" + name + ".txt", ask)).read()
    body = t[t.find("$$SOE") + 5:t.find("$$EOE")]
    out = []
    for l in body.strip().splitlines():
        f = [x.strip() for x in l.split(",")]
        out.append((float(f[0]), [float(x) for x in f[2:] if x]))
    return out

def simbad(name, adql):
    def ask():
        q = urllib.parse.urlencode({"request": "doQuery", "lang": "adql", "format": "csv", "query": adql})
        return get("https://simbad.cds.unistra.fr/simbad/sim-tap/sync?" + q)
    import csv
    return list(csv.DictReader(io.StringIO(open(cached("simbad_" + name + ".csv", ask), encoding="utf-8").read())))


# ---- the stars -------------------------------------------------------------
def distances():
    """How far each star of the catalogue is: its parallax in SIMBAD, by its number in the catalogue (HR).
    Where a star has none of its own (the two stars of a pair often do not), that of the pair it belongs to."""
    num = lambda r: int(r["id"].replace("HR", ""))
    P, at = {}, {}
    for r in simbad("hr", "SELECT ident.id, basic.ra, basic.dec, basic.plx_value FROM ident JOIN basic ON ident.oidref = basic.oid WHERE ident.id LIKE 'HR %'"):
        try: n = num(r)
        except ValueError: continue
        if r["ra"] and r["dec"]: at[n] = (float(r["ra"]), float(r["dec"]))
        if r["plx_value"]: P[n] = float(r["plx_value"])
    for r in simbad("hr_parents", "SELECT ident.id, basic.main_id, basic.plx_value FROM ident JOIN h_link ON ident.oidref = h_link.child "
                                  "JOIN basic ON h_link.parent = basic.oid WHERE ident.id LIKE 'HR %' AND basic.plx_value IS NOT NULL"):
        try: n = num(r)
        except ValueError: continue
        if n not in P: P[n] = float(r["plx_value"])
    # and failing that, the star beside it
    for n, (ra, de) in at.items():
        if n in P: continue
        for m in (n - 1, n + 1, n - 2, n + 2):
            if m in P and m in at and math.hypot((at[m][0] - ra) * math.cos(de * D2R), at[m][1] - de) < 0.03:
                P[n] = P[m]; break
    return P

def near():
    """The neighbours: right ascension, declination, parallax (mas), brightness V, colour B-V."""
    ids = ",".join("'%s'" % v[0].replace("'", "''") for v in NEAR.values())
    rows = simbad("near", "SELECT ident.id, ra, dec, plx_value, V, B FROM ident JOIN basic ON ident.oidref = basic.oid "
                          "LEFT JOIN allfluxes ON basic.oid = allfluxes.oidref WHERE ident.id IN (%s)" % ids)
    squeeze = lambda t: re.sub(r"\s+", " ", t.strip())
    by = {squeeze(r["id"]): r for r in rows}
    out = {}
    for k, v in NEAR.items():
        r = by.get(squeeze(v[0]))
        if not r or not r["plx_value"]: sys.exit("SIMBAD has no distance for " + v[0])
        V = float(r["V"]) if r["V"] else (v[1] if len(v) > 1 else None)
        bv = v[2] if len(v) > 2 else (float(r["B"]) - float(r["V"]) if r["V"] and r["B"] else None)
        if V is None or bv is None: sys.exit("no brightness for " + v[0])
        out[k] = [round(float(r["ra"]), 5), round(float(r["dec"]), 5), round(float(r["plx_value"]), 3), round(V, 2), round(bv, 2)]
    print("  neighbours: %d, from %.2f to %.2f light-years" % (len(out), min(1000 * LY_PC / v[2] for v in out.values()),
                                                              max(1000 * LY_PC / v[2] for v in out.values())))
    return out

def stars(nr, limit=5.6):
    raw = gzip.open(source("bsc5.dat.gz")).read().decode("latin-1")
    P = distances()
    S = []
    for l in raw.splitlines():
        try:
            ra = (int(l[75:77]) + int(l[77:79]) / 60 + float(l[79:83]) / 3600) * 15
            de = (int(l[84:86]) + int(l[86:88]) / 60 + int(l[88:90]) / 3600) * (-1 if l[83] == "-" else 1)
            v = float(l[102:107])
        except ValueError:
            continue                                  # the catalogue keeps a few entries that are not stars
        try: bv = float(l[109:114])
        except ValueError: bv = 0.6
        plx = P.get(int(l[0:4]), 0)
        # a neighbour with a name stands where its name stands
        for n in nr.values():
            if n[3] < 6.5 and math.hypot((n[0] - ra) * math.cos(de * D2R), n[1] - de) < 0.03: plx = n[2]
        S.append((v, ra, de, bv, plx))
    S.sort()
    out, known = bytearray(), 0
    for v, ra, de, bv, plx in S:
        if v > limit: break
        a, d = ra * D2R, de * D2R
        x, y, z = math.cos(d) * math.cos(a), math.cos(d) * math.sin(a), math.sin(d)
        ye, ze = math.cos(EPS) * y + math.sin(EPS) * z, -math.sin(EPS) * y + math.cos(EPS) * z
        lon, lat = math.atan2(ye, x) % (2 * math.pi), math.asin(max(-1, min(1, ze)))
        # how far, in light-years, on a scale of logarithms: 1 is one light-year, 65535 is 15,849. 0: too far to tell
        far = 0
        if plx >= 0.2:
            far = 1 + int(round(max(0, min(1, math.log10(1000 * LY_PC / plx) / 4.2)) * 65534)); known += 1
        out += struct.pack("<HHBBH", int(round(lon / (2 * math.pi) * 65536)) % 65536, int(round((lat / math.pi + 0.5) * 65535)),
                           max(0, min(255, int(round((v + 1.5) * 30)))), max(0, min(255, int(round((bv + 0.4) * 100)))), far)
    print("  stars: %d to magnitude %.1f, %d bytes; the distance is known for %d" % (len(out) // 8, limit, len(out), known))
    return base64.b64encode(bytes(out)).decode()


# ---- the maps ----------------------------------------------------------------
# how many pixels across each map is kept, and how hard it is squeezed (WebP).
# A globe beside which the eye has arrived is about 570 pixels across on a
# laptop and shows half its map: 1024 across is the least that is not a blur,
# 2048 stays sharp when the eye comes closer.
KEEP = {"earth": (2048, 65), "land": (2048, 0), "clouds": (1024, 50), "night": (1024, 60), "moon": (2048, 50),
        "mars": (2048, 50), "jupiter": (2048, 65), "mercury": (1024, 50), "pluto": (1024, 65),
        "io": (2048, 55), "europa": (1024, 60), "ganymede": (1024, 60), "callisto": (1024, 60), "milkyway": (2048, 60)}


def read_exr(path):
    """The one kind of OpenEXR file NASA's star maps are: scanlines, ZIP, half
    floats. -> width, height, rows of (R, G, B), each a tuple of floats."""
    d = open(path, "rb").read()
    assert d[:4] == b"\x76\x2f\x31\x01", "not an OpenEXR file"
    p = 8; chans = []; comp = None; win = None
    while True:
        e = d.index(b"\0", p); name = d[p:e].decode(); p = e + 1
        if not name: break
        e = d.index(b"\0", p); typ = d[p:e].decode(); p = e + 1
        size = struct.unpack("<I", d[p:p + 4])[0]; p += 4; val = d[p:p + size]; p += size
        if typ == "compression": comp = val[0]
        elif typ == "chlist":
            q = 0
            while val[q] != 0:
                e2 = val.index(b"\0", q); chans.append((val[q:e2].decode(), struct.unpack("<I", val[e2 + 1:e2 + 5])[0])); q = e2 + 17
        elif name == "dataWindow": win = struct.unpack("<4i", val)
    assert comp == 3 and all(t == 1 for _, t in chans), "only ZIP-compressed half floats are read here"
    W = win[2] - win[0] + 1; H = win[3] - win[1] + 1; n = len(chans); names = [c for c, _ in chans]
    blocks = (H + 15) // 16
    rows = [None] * H
    for o in struct.unpack("<%dQ" % blocks, d[p:p + 8 * blocks]):
        y, size = struct.unpack("<ii", d[o:o + 8]); raw = zlib.decompress(d[o + 8:o + 8 + size])
        # undo the predictor (a running sum) and the split into odd and even bytes
        t = bytes(itertools.accumulate(raw, lambda a, b: (a + b - 128) & 255))
        half = (len(t) + 1) // 2; out = bytearray(len(t)); out[0::2] = t[:half]; out[1::2] = t[half:]
        for k in range(len(out) // (W * 2 * n)):
            base = k * W * 2 * n
            ch = {nm: struct.unpack("<%de" % W, out[base + i * W * 2: base + (i + 1) * W * 2]) for i, nm in enumerate(names)}
            rows[y + k] = (ch["R"], ch["G"], ch["B"])
    return W, H, rows

def maps():
    from PIL import Image, ImageFilter, ImageChops, ImageMath, ImageDraw, ImageStat
    Image.MAX_IMAGE_PIXELS = None
    OUT = {}
    def enc(name, im):
        b = io.BytesIO(); im.save(b, "WEBP", quality=KEEP[name][1], method=6)
        OUT[name] = base64.b64encode(b.getvalue()).decode()
        print("  %-8s %s %6d bytes" % (name, im.size, len(b.getvalue())))
    def fit(im, name):
        w = KEEP[name][0]
        return im.resize((w, w // 2), Image.LANCZOS)
    def over(a, b):
        """a / b, 0..255, channel by channel, where b is a coverage 0..255"""
        f = lambda A, B: ImageMath.lambda_eval(lambda _: _["convert"](_["min"](_["float"](_["a"]) * 255.0 / _["max"](_["float"](_["b"]), 1.0), 255.0), "L"), a=A, b=B)
        return Image.merge("RGB", [f(c, b) for c in a.split()]) if a.mode == "RGB" else f(a, b)
    def carried(im, known, reach):
        """the picture, with what is known of it carried into what is not: beside
        the known ground its own colours, far from any of it the colour of all of
        it together. (Dividing by a coverage of almost nothing makes rainbows.)"""
        pre = Image.merge("RGB", [ImageChops.multiply(c, known) for c in im.split()])
        cover = known.filter(ImageFilter.GaussianBlur(reach))
        near = over(pre.filter(ImageFilter.GaussianBlur(reach)), cover)
        total = max(1.0, ImageStat.Stat(known).sum[0])
        far = Image.new("RGB", im.size, tuple(int(min(255, v * 255.0 / total)) for v in ImageStat.Stat(pre).sum))
        how = cover.point(lambda v: 0 if v < 24 else min(255, (v - 24) * 6))
        return Image.composite(im, Image.composite(near, far, how), known.point(lambda v: 255 if v >= 128 else 0))

    # Earth. The map paints the sea black: keep the land's own colour right up
    # to the shore (and a little past it), and carry the shoreline in a mask of
    # its own. Otherwise every coast is drawn with a dark line.
    e = Image.open(source("earth_topo.jpg")).convert("RGB")
    r, g, b = e.split()
    hi = ImageChops.lighter(r, g).point(lambda v: 255 if v >= 16 else 0)
    W = KEEP["earth"][0]
    mask = hi.resize((W, W // 2), Image.BOX)
    pre = Image.merge("RGB", [ImageChops.multiply(c, hi) for c in (r, g, b)]).resize((W, W // 2), Image.BOX)
    land = over(pre, mask)
    solid = mask.point(lambda v: 255 if v >= 20 else 0)
    day = carried(land, solid, W / 512 * 2.5)
    enc("earth", day)
    q = fit(hi, "land") if KEEP["land"][0] != W else mask
    q = q.point(lambda v: int(round(v / 255 * 3)) * 85).convert("P", palette=Image.ADAPTIVE, colors=4)
    bb = io.BytesIO(); q.save(bb, "PNG", optimize=True)
    OUT["land"] = base64.b64encode(bb.getvalue()).decode()
    print("  %-8s %s %6d bytes (png)" % ("land", q.size, len(bb.getvalue())))

    enc("clouds", fit(Image.open(source("earth_clouds.jpg")).convert("L"), "clouds"))

    # the lights of the cities: keep the lights, drop the moonlit land the composite carries
    r, g, b = Image.open(source("earth_night.jpg")).convert("RGB").split()
    lum = ImageChops.lighter(r, g).point(lambda v: 0 if v < 46 else min(255, int((v - 46) * 1.9)))
    W = KEEP["night"][0]
    lum = lum.resize((W * 2, W), Image.BOX).filter(ImageFilter.GaussianBlur(0.8)).resize((W, W // 2), Image.BOX)
    lum = lum.point(lambda v: min(255, int((v / 255.0) ** 0.6 * 255 * 1.25)))
    ice = Image.new("L", (1, W // 2))                 # and none on the ice
    for y in range(W // 2):
        lat = 90 - (y + 0.5) / (W // 2) * 180
        k = 0.0 if (lat < -57 or lat > 74) else (min(1.0, (lat + 57) / 4.0) if lat < -53 else (min(1.0, (74 - lat) / 4.0) if lat > 70 else 1.0))
        ice.putpixel((0, y), int(k * 255))
    enc("night", ImageChops.multiply(lum, ice.resize((W, W // 2))))

    enc("moon", fit(Image.open(source("moon.tif")).convert("L"), "moon"))
    enc("mars", fit(Image.open(source("mars_2560.jpg")).convert("RGB"), "mars"))
    enc("jupiter", fit(Image.open(source("jupiter_2560.jpg")).convert("RGB"), "jupiter"))

    # Mercury: the mosaic leaves the poles black. Carry the nearest mapped ground into them.
    me = fit(Image.open(source("mercury_2560.png")).convert("L"), "mercury").convert("RGB")
    W, H = me.size
    known = me.convert("L").point(lambda v: 255 if v > 40 else 0)
    cap = Image.new("L", (W, H), 255); d = ImageDraw.Draw(cap)       # only the polar caps can be unmapped
    d.rectangle([0, int(H * 0.07), W, int(H * 0.93)], fill=0)
    known = ImageChops.lighter(known, ImageChops.invert(cap)).filter(ImageFilter.MinFilter(9))
    enc("mercury", carried(me, known, W / 256 * 3).convert("L"))

    # Pluto: the far south was in winter night when New Horizons passed, and is
    # black on the map. What is put there is the colour of the ground beside
    # it, without features: it is not terrain, and the page says so.
    p = fit(Image.open(source("pluto_2560.jpg")).convert("RGB"), "pluto")
    W, H = p.size
    dark = p.convert("L").point(lambda v: 0 if v < 12 else 255)      # 0 where black
    seen = dark.copy()
    for x in range(0, W, 8):                                         # the black that is joined to the bottom edge
        if seen.getpixel((x, H - 1)) == 0: ImageDraw.floodfill(seen, (x, H - 1), 128, thresh=0)
    known = seen.point(lambda v: 0 if v == 128 else 255)
    k = int(W / 256 * 2) * 2 + 1
    known = known.filter(ImageFilter.MinFilter(k))                   # the pixels beside the black are half black themselves
    enc("pluto", carried(p, known, W / 256 * 3))

    # The four large moons of Jupiter, from the USGS mosaics of Voyager and
    # Galileo pictures. Where neither spacecraft saw the ground (the poles,
    # mostly) the mosaic is black: the ground beside it is carried in, without
    # features. The seams between pictures taken in different light are in the
    # mosaics themselves, and are left as they are.
    for name in ("io", "europa", "ganymede", "callisto"):
        m = fit(Image.open(source(name + ".tif")).convert("RGB"), name)
        W, H = m.size
        known = m.convert("L").point(lambda v: 0 if v < 6 else 255).filter(ImageFilter.MinFilter(int(W / 512) * 2 + 3))
        m = carried(m, known, W / 256 * 3)
        enc(name, m if name == "io" else m.convert("L"))

    # The Milky Way: NASA's Deep Star Maps 2020, made from the stars Gaia
    # counted, in right ascension and declination. The faint even glow of the
    # whole sky is taken off (this page's sky is black between the stars), the
    # bright end is squeezed, and what is kept is the square root, so that the
    # dark end gets most of the 256 steps.
    W, H, rows = read_exr(source("milkyway_4k.exr"))
    w = KEEP["milkyway"][0]; step = W // w
    sky = Image.new("RGB", (w, w // 2)); px = sky.load()
    for y in range(0, H, step):
        band = rows[y:y + step]
        for x in range(0, W, step):
            c = []
            for ch in range(3):
                v = sum(sum(r[ch][x:x + step]) for r in band) / (step * step)
                c.append(min(255, int(math.sqrt(min(1.0, 0.30 * max(0.0, v - 0.012) ** 0.6)) * 255 + 0.5)))
            px[x // step, y // step] = tuple(c)
    enc("milkyway", sky)
    print("  maps: %d bytes as text" % sum(len(v) for v in OUT.values()))
    return OUT


# ---- the moons -----------------------------------------------------------------
def cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def dot(a, b): return sum(x * y for x, y in zip(a, b))
def unit(a):
    l = math.sqrt(dot(a, a)); return tuple(x / l for x in a)
def angle(a, b): return math.degrees(math.acos(max(-1, min(1, dot(a, b) / math.sqrt(dot(a, a) * dot(b, b))))))

def lsq(F, y):
    k = len(F[0])
    A = [[sum(f[i] * f[j] for f in F) for j in range(k)] + [sum(f[i] * v for f, v in zip(F, y))] for i in range(k)]
    for i in range(k):
        p = max(range(i, k), key=lambda r: abs(A[r][i])); A[i], A[p] = A[p], A[i]
        for r in range(i + 1, k):
            f = A[r][i] / A[i][i]
            for j in range(i, k + 1): A[r][j] -= f * A[i][j]
    x = [0] * k
    for i in range(k - 1, -1, -1): x[i] = (A[i][k] - sum(A[i][j] * x[j] for j in range(i + 1, k))) / A[i][i]
    return x

def moon_states(name, which):
    i, c = MOONS[name]
    if which == "fit":       # fifteen years, a sample every 92 days: no moon keeps step with that
        return horizons("fit_" + name, COMMAND=i, EPHEM_TYPE="VECTORS", CENTER="500@%d" % c, START_TIME="2019-01-01",
                        STOP_TIME="2034-06-01", STEP_SIZE="2207 h", OUT_UNITS="KM-D", VEC_TABLE="2")
    return horizons("mv_" + name, COMMAND=i, EPHEM_TYPE="VECTORS", CENTER="500@%d" % c, START_TIME="2026-09-28",
                    STOP_TIME="2027-09-28", STEP_SIZE="73 d", OUT_UNITS="KM-D", VEC_TABLE="1")

def moons():
    """Each moon as a fixed ellipse: mean distance, mean motion, where it stood on JD0, and the plane it keeps."""
    out = {}
    for nm in MOONS:
        S = moon_states(nm, "fit")
        n = [0, 0, 0]
        for jd, v in S:
            h = unit(cross(v[:3], v[3:6])); n = [n[i] + h[i] for i in range(3)]
        n = unit(n)
        e1 = unit(cross((0, 0, 1), n)); e2 = cross(n, e1)
        # a first guess at the mean motion from two states a quarter of a day apart would do; the speed gives it directly
        n0 = sum(math.sqrt(dot(v[3:6], v[3:6])) / math.sqrt(dot(v[:3], v[:3])) for jd, v in S) / len(S)
        th, ts, rr, prev = [], [], [], None
        for jd, v in S:
            a = math.atan2(dot(v[:3], e2), dot(v[:3], e1))
            if prev is not None:
                a += 2 * math.pi * round((prev[1] + n0 * (jd - prev[0]) - a) / (2 * math.pi))
            prev = (jd, a); th.append(a); ts.append(jd - JD0); rr.append(math.sqrt(dot(v[:3], v[:3])))
        t0, nn = lsq([[1, t] for t in ts], th)
        for it in range(3):
            t0, nn, A, B = lsq([[1, t, math.sin(t0 + nn * t), math.cos(t0 + nn * t)] for t in ts], th)
        e, w = math.hypot(A, B) / 2, math.atan2(-B, A) % (2 * math.pi)
        a_mean = sum(rr) / len(rr)
        t0 %= 2 * math.pi
        worst = 0
        for jd, v in moon_states(nm, "check"):
            m = t0 + nn * (jd - JD0); g = m + 2 * e * math.sin(m - w); r = a_mean * (1 - e * math.cos(m - w))
            worst = max(worst, angle([r * (math.cos(g) * e1[i] + math.sin(g) * e2[i]) for i in range(3)], v[:3]))
        print("  %-10s every %10.6f days, %9.0f km, within %.2f deg of Horizons over the year after JD0" % (nm, 2 * math.pi / nn, a_mean, worst))
        out[nm] = [round(a_mean, 1), float("%.10g" % nn), round(t0, 5), round(e, 4), round(w, 4), round(n[0], 5), round(n[1], 5), round(n[2], 5)]
    return out


# ---- the spacecraft ----------------------------------------------------------
GM = 0.01720209895 ** 2               # the Sun's pull, au^3 / day^2

def craft_states(name, since=None):
    i, free = CRAFT[name]
    if since is None:
        return horizons("craft_" + name, COMMAND=i, EPHEM_TYPE="VECTORS", CENTER="500@10", START_TIME="2026-09-28",
                        STOP_TIME="2029-09-28", STEP_SIZE="1 y", OUT_UNITS="AU-D", VEC_TABLE="2")
    return horizons("craft_was_" + name, COMMAND=i, EPHEM_TYPE="VECTORS", CENTER="500@10", START_TIME=free,
                    STOP_TIME="2026-09-28", STEP_SIZE="3 y", OUT_UNITS="AU-D", VEC_TABLE="2")

def leaving(r, v, days):
    """Where a body that is leaving the Sun for good will be, `days` from the moment it was at r going at v."""
    rl = math.sqrt(dot(r, r)); h = cross(r, v)
    ev = [a / GM - b / rl for a, b in zip(cross(v, h), r)]
    e = math.sqrt(dot(ev, ev)); a = 1 / (dot(v, v) / GM - 2 / rl)
    Pv = unit(ev); Q = cross(unit(h), Pv)
    H = math.asinh(dot(r, Q) / (a * math.sqrt(e * e - 1)))
    M = e * math.sinh(H) - H + math.sqrt(GM / a ** 3) * days
    H = math.asinh(M / e)
    for _ in range(40): H -= (e * math.sinh(H) - H - M) / (e * math.cosh(H) - 1)
    x, y = a * (e - math.cosh(H)), a * math.sqrt(e * e - 1) * math.sinh(H)
    return [Pv[k] * x + Q[k] * y for k in range(3)]

def craft():
    """Each spacecraft: where it was on JD0 and how fast it was going (from the Sun, the ecliptic of J2000, au and au a day),
    and the day its last encounter was behind it. The page draws the curve through that."""
    out = {}
    for nm, (i, free) in CRAFT.items():
        S = craft_states(nm)
        jd, v = S[0]
        if abs(jd - JD0) > 1e-6: sys.exit("Horizons did not begin %s on JD0" % nm)
        t = time.strptime(free, "%Y-%m-%d")
        a = (14 - t.tm_mon) // 12; y = t.tm_year + 4800 - a; m = t.tm_mon + 12 * a - 3
        since = t.tm_mday + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045 - 0.5
        worst = (0, 0)
        for j, w in craft_states(nm, since=True) + S[1:]:
            p = leaving(v[:3], v[3:6], j - JD0)
            miss = math.sqrt(sum((p[k] - w[k]) ** 2 for k in range(3)))
            if miss > worst[0]: worst = (miss, j)
        print("  %-12s %7.2f au from the Sun, %5.2f km/s; from %s to 2029 never more than %.2f au from Horizons (worst on JD %.0f)"
              % (nm, math.sqrt(dot(v[:3], v[:3])), math.sqrt(dot(v[3:6], v[3:6])) * AU / 86400, free, worst[0], worst[1]))
        out[nm] = [float("%.9g" % x) for x in v[:6]] + [since]
    return out


# ---- writing the page --------------------------------------------------------------
def write(page, st, mp, mf, nr, cr):
    s = open(page, encoding="utf-8").read()
    def put(pattern, text, what):
        nonlocal s
        s, n = re.subn(pattern, lambda m: text, s, count=1, flags=re.S)
        if n != 1: sys.exit("could not find the %s block in %s" % (what, page))
    put(r"const STARS = '[^']*';", "const STARS = '%s';" % st, "STARS")
    put(r"const MAPS = \{.*?\n  \};", "const MAPS = {\n%s\n  };" % ",\n".join("    %s: '%s'" % kv for kv in mp.items()), "MAPS")
    put(r"const MOON_FIT = \{.*?\n  \};", "const MOON_FIT = {\n%s  };" % "".join("    %s: %s,\n" % (k, json.dumps(v)) for k, v in mf.items()), "MOON_FIT")
    put(r"const NEAR = \{.*?\n  \};", "const NEAR = {\n%s  };" % "".join("    %s: %s,\n" % (k, json.dumps(v)) for k, v in nr.items()), "NEAR")
    put(r"const CRAFT = \{.*?\n  \};", "const CRAFT = {\n%s  };" % "".join("    %s: %s,\n" % (k, json.dumps(v)) for k, v in cr.items()), "CRAFT")
    open(page, "w", encoding="utf-8").write(s)
    print("wrote", page, len(s.encode()), "bytes")


# ---- checking the formulas (the same ones the page uses, in Python) --------------------
def check(page):
    s = open(page, encoding="utf-8").read()
    grab = lambda name: json.loads(re.sub(r"(\w+):", r'"\1":', re.search(r"const %s = (\{.*?\n  \});" % name, s, re.S).group(1)).replace(",\n  }", "\n  }"))
    EL, EX = grab("EL"), grab("EL_EXTRA")
    def kepler(M, e):
        M = (M + math.pi) % (2 * math.pi) - math.pi
        E = M + e * math.sin(M)
        for _ in range(40): E -= (E - e * math.sin(E) - M) / (1 - e * math.cos(E))
        return E
    def planet(k, jd):
        T = (jd - 2451545.0) / 36525; el = EL[k]
        a, e, I, L, lp, ln = [el[j] + el[j + 6] * T for j in range(6)]
        M = L - lp
        if k in EX:
            b, c, sn, f = EX[k]; M += b * T * T + c * math.cos(f * T * D2R) + sn * math.sin(f * T * D2R)
        E = kepler(M * D2R, e); x = a * (math.cos(E) - e); y = a * math.sqrt(1 - e * e) * math.sin(E)
        w, O, i = (lp - ln) * D2R, ln * D2R, I * D2R
        cw, sw, cO, sO, ci, si = math.cos(w), math.sin(w), math.cos(O), math.sin(O), math.cos(i), math.sin(i)
        return ((cw * cO - sw * sO * ci) * x + (-sw * cO - cw * sO * ci) * y, (cw * sO + sw * cO * ci) * x + (-sw * sO + cw * cO * ci) * y, sw * si * x + cw * si * y)
    print("planets against Horizons, thirteen dates from 1990 to 2062:")
    for k, i in PLANETS.items():
        H = horizons("vec_" + k, COMMAND=i, EPHEM_TYPE="VECTORS", CENTER="500@10", START_TIME="1990-01-01", STOP_TIME="2062-01-01",
                     STEP_SIZE="6 y", OUT_UNITS="AU-D", VEC_TABLE="1")
        print("  %-8s within %.3f deg" % (k, max(angle(planet(k, jd), v[:3]) for jd, v in H)))
    print("(the Moon, the spin axes and the moons are checked in the page itself: open it and ask window.__solar.where('moon'))")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "build" and len(sys.argv) > 2:
        print("cache:", CACHE)
        nr = near()
        write(sys.argv[2], stars(nr), maps(), moons(), nr, craft())
    elif cmd == "check" and len(sys.argv) > 2:
        check(sys.argv[2])
    elif cmd == "sheet" and len(sys.argv) > 3:
        from PIL import Image
        s = open(sys.argv[2], encoding="utf-8").read()
        mp = dict(re.findall(r"    (\w+): '([A-Za-z0-9+/=]+)'", re.search(r"const MAPS = \{(.*?)\n  \};", s, re.S).group(1)))
        sheet = Image.new("RGB", (1536, 256 * ((len(mp) + 2) // 3)))
        for i, (k, v) in enumerate(mp.items()):
            sheet.paste(Image.open(io.BytesIO(base64.b64decode(v))).convert("RGB").resize((512, 256)), ((i % 3) * 512, (i // 3) * 256))
        sheet.save(sys.argv[3]); print("wrote", sys.argv[3])
    else:
        sys.exit(__doc__)
