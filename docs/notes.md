For your toy model, I'd recommend zeroing in on the High Rhine (Oberrhein) sub-basin, specifically around the Laufenburg hydropower plant on the Swiss-German border. This stretch of the Rhine is hydropower-heavy with multiple dams (like Laufenburg, which generates ~100 MW across Swiss and German sides), and it's upstream in the basin—meaning precip here directly impacts reservoir inflows for downstream energy storage and generation in Germany/France. It's a compact, representative spot for Europe (avoids sprawling the whole 185,000 km² basin), and easy to grid-point for GEFS/ERA5.

We will focus on the High Rhine sub-basin, around the Laufenburg hydropower plant on the Swiss-German border. A https://www.iksr.org/en/topics/rhine/sub-basins/high-rhine

Laufenburg is city that is in both Switzerland and Germany, it is split by the
Rhine River. The location is 47.5565 N, 8.0483 E.

# Dev notes:

2025-12-18:
Fixed an error in the GEFS aggregator where the end_hour was inclusive. For example, for the lead 120-144 window, it was using the 144 hour forecast, which is for hours 144-147. So, we were actually getting the TP for 120 through 147, which is wrong, we just want 120 through 144, so the last GEFS forecast hour that we want is 141.

Next I need to attach to the EC2 instance I had running to download more GEFS data to see what data we have and can download.
