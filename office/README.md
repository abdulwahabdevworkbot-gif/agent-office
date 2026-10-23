# Office dashboard template

`office.html` is the product office page that the `office-manager` session publishes as a private claude.ai Artifact (capabilities `db` + `user` + `sample`; `sample` gives the quick replies).

Every requirement for the page and its data layout is in `SPEC.md`.

- Publish `office.html` as the page and every file under `assets/` with the same relative paths (Artifact `files`).
- The page title is "Product Office". To show the product's name, write `meta/office` with `{ "product_en": "<name>" }` to the page's database.
- The whole page is English, left to right. Agents show by `name_en`, `role_en`, `doing_en`; tasks by `feature` and `title_en`. Full requirements: playbook card 0d. Font: Dubai (`assets/fonts/`). Thmanyah is not used because its license forbids hosting the font files.
- Data collections: `agents`, `tasks`, `messages`, `sessions` (schema in the playbook, section 8, card 0d).
- Rooms: the manager's office (owner + `office-manager` as the assistant; agents in state `waiting` visit here), the meeting room (agents talking to each other and members of open task sessions sit at the table), the main office (working and blocked agents on chairs at desks), the games room (done and not started agents), and the idle room (agents with no activity for more than 3 days sit there on chairs, still, with "Idle since <date>"). Agents walk between rooms when their state changes.
- Task sessions: the owner opens one from a task when something isn't clear; it is private to that question and closes when it is solved.

Art credits: office room, furniture, effects and character sprites from [W17ant/Claude-Office](https://github.com/W17ant/Claude-Office) (MIT). Only the MIT-licensed art is used; none of the excluded fan-art from that repo. The games room furniture is drawn by `tools/game_room.py`, and the meeting room, conference table and chairs by `tools/meeting_room.py`, on top of the same room.
