# Credits

`index.html` carries other people's measurements and pictures inside it;
this is where each comes from. All of the pictures are public domain (work of NASA and the
USGS). Two sources ask to be named: the Gaia mission, whose star counts are
under the map of the Milky Way and whose parallaxes are most of the
distances of the stars, and SIMBAD, which the distances were read from. The
rest are named anyway, for the same reason as the sounds.

| Inside the page | What it is | Source |
|---|---|---|
| `MAPS.earth`, `MAPS.land` | Earth's ground and shoreline | NASA Earth Observatory — Blue Marble: Next Generation, July 2004 (R. Stöckli) |
| `MAPS.clouds` | Earth's clouds | NASA Earth Observatory — Blue Marble cloud composite |
| `MAPS.night` | the lights of the cities | NASA Earth Observatory / NOAA — Black Marble 2016 (Suomi NPP) |
| `MAPS.moon` | the Moon | NASA Goddard Scientific Visualization Studio — CGI Moon Kit, LRO/LROC colour mosaic |
| `MAPS.mars` | Mars | NASA / JPL / USGS — Viking MDIM 2.1 colour mosaic |
| `MAPS.jupiter` | Jupiter | NASA / JPL / Space Science Institute — Cassini, PIA07782 |
| `MAPS.mercury` | Mercury | NASA / JHUAPL / Carnegie Institution — MESSENGER global mosaic |
| `MAPS.pluto` | Pluto | NASA / JHUAPL / SwRI — New Horizons colour mosaic |
| `MAPS.io` | Io | USGS Astrogeology — Galileo SSI / Voyager global colour mosaic, 1 km (NASA / JPL / USGS) |
| `MAPS.europa` | Europa | USGS Astrogeology — Voyager / Galileo SSI global mosaic, 500 m (NASA / JPL / USGS) |
| `MAPS.ganymede` | Ganymede | USGS Astrogeology — Voyager / Galileo SSI global mosaic, 1 km (NASA / JPL / USGS) |
| `MAPS.callisto` | Callisto | USGS Astrogeology — Voyager / Galileo SSI global mosaic, 1 km (NASA / JPL / USGS) |
| `MAPS.milkyway` | the Milky Way and the Magellanic Clouds | NASA/Goddard Space Flight Center Scientific Visualization Studio — Deep Star Maps 2020. Gaia DR2: ESA/Gaia/DPAC |
| `STARS` | 3,249 stars to magnitude 5.6 | Yale Bright Star Catalogue, 5th ed. (Hoffleit & Warren), via CDS Strasbourg, catalogue V/50 |
| `STARS`, the last two bytes of each | how far each of them is | the SIMBAD database, CDS, Strasbourg Astronomical Observatory, France: parallaxes, most of them measured by ESA's Hipparcos (the 2007 reduction, F. van Leeuwen) and Gaia (ESA/Gaia/DPAC) |
| `NEAR` | the stars and brown dwarfs within twelve light-years, and Altair, Vega and Fomalhaut: where, how far, how bright | the SIMBAD database, CDS, Strasbourg Astronomical Observatory, France |
| `CRAFT` | Voyager 1 and 2, Pioneer 10 and 11, New Horizons: where each was on 28 September 2026, and how fast it was going | the JPL Horizons system |
| `EL`, `EL_EXTRA` | the orbits of the planets | JPL Solar System Dynamics — "Approximate Positions of the Planets" (E. M. Standish & J. G. Williams) |
| `MOON_FIT`, `SMALL` | the orbits of the moons, dwarf planets and comets | fitted to, or read from, the JPL Horizons system |
| `MOON_LR`, `MOON_B` | the Moon's own motion | the larger terms of the lunar theory as given in J. Meeus, *Astronomical Algorithms* |
| `ROT` | how each body is turned | IAU Working Group on Cartographic Coordinates and Rotational Elements |
| `magOf` | how bright each planet is in your own sky | the formulas of the *Astronomical Almanac*, as given in J. Meeus, *Astronomical Algorithms* |

None of the maps is the original file. Each was reduced to 2048 or 1024
pixels across and re-encoded (WebP; the shoreline is a PNG), and some were
changed beyond that:

- Earth's map has its land colour carried a little past every shore (the
  shoreline is in `MAPS.land`).
- Where no spacecraft saw the ground, the source is black, and the colour of
  the ground beside it is carried in without features: Mercury's poles, the
  poles of Jupiter's four moons, and the far south of Pluto, which was in
  winter night when New Horizons passed. None of that is terrain.
- Three of the moons' mosaics (Europa, Ganymede, Callisto) are grey; the page
  tints them. The seams between pictures taken in different light are in the
  mosaics themselves and are left as they are.
- The Milky Way has the faint even glow of the whole sky taken off and its
  bright end squeezed, so that it sits quietly behind everything else.

Mars, Mercury, Jupiter and Pluto were fetched from Wikimedia Commons, where
each is marked public domain. `tools/solar_data.py` fetches every source
again and rebuilds the data byte for byte.

Venus, Saturn and its rings, Uranus, Neptune, Titan and the smaller moons
wear no map: they are painted by the page's own shaders. (Titan has a map,
but of its ground in infrared; to the eye it is haze.) Andromeda is drawn,
at its measured place, size and tilt.

Two things past the planets are drawn and not measured, and the page says
so where it names them. The edge of the Sun's wind is a round shell 120 au
out because that is where it was crossed: by Voyager 1 at 121.6 au in August
2012 and by Voyager 2 at 119.0 au in November 2018 (NASA / JPL). Its shape
on the side away from them is not known, and that side is left open. The
Oort cloud has never been observed; what is drawn is the usual reckoning of
it, from 2,000 to 100,000 au.

What is said of each neighbouring star (that Barnard's Star crosses the sky
faster than any other, that 61 Cygni was the first star whose distance was
measured) is common knowledge of astronomy and is the page's own wording.
