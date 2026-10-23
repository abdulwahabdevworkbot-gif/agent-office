# Cutting the owner's art

The rooms, characters and seated poses are the owner's own pictures. These scripts cut them out of the owner's sheets; they never redraw anything.

1. Put the owner's sheets in `src/`:
   - `chars41.png`: the 41 characters;
   - `rooms1.png` and `rooms2.png`: the room sheets;
   - `seated.png`: the seated pose library.
   The sheets are not kept in the repo.
2. Run, from this folder:

```
python3 cut41.py       # characters  -> n41/raw*.png
python3 export.py      # characters  -> ../../assets/chars (+ the small credit tag), rooms -> ../../assets/rooms
python3 rooms.py && python3 roomcanvas.py   # rooms cut out, placed on the 1200x896 canvas with the clear credit tag (run before export.py)
python3 seatcut.py && python3 heads2.py && python3 seatexport.py   # seated bodies and heads -> ../../assets/seated, ../../assets/heads
```

Needs Python with Pillow, numpy and scipy. Every output carries the credit tag `@Abdulwahabdev` (see the root `LICENSE`).

After changing `characters.json` or `seated.json`, copy them into the `CHARS` and `SEATED` constants in `office.html`.
