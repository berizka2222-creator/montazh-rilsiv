# Монтаж тексту на відео

**TARGET AI · Етап 4 · урок 4.7.** Рушій для скілу `montazh-tekstu`: редактор із таймлайном і рендер готового відеокреативу з текстом, що з'являється по черзі.

Скіл сам завантажує цю папку, нічого ставити руками не треба.

## Що тут
| Файл | Що робить |
|---|---|
| `editor.html` | Редактор: відео, таймлайн, кожен рядок окремим шаром, 14 стилів, підкладки, декор, фони, картинки й відео поверх, «за людиною», нарізка відео. Він же малює кадри для рендеру (`?render=1`). |
| `render.py` | Рендер проєкту в MP4 9:16 і 4:5 зі звуком. |
| `apply_pack.py` | Застосовує стиль до проєкту без відкриття редактора (`--list` — усі стилі). |
| `build_artifact.py` | Збирає редактор з відео в один HTML-файл, щоб відкрити його в чаті. |
| `make_matte.py` | Вирізає людину з відео (тільки потрібні секунди) для шарів «за людиною». |
| `thumbs.py` | Прев'ю стилів на чорному фоні (`thumbs/`, `thumbs.js`). |
| `fonts/`, `fontlib/` | Безкоштовні шрифти з кирилицею (Google Fonts, ліцензія SIL OFL 1.1). |
| `brand/` | Сюди кладуться шрифти бренду: `brand/fonts.css` з `@font-face` для сімей `Brand Sans` і `Brand Serif`. Без них редактор бере Manrope і Playfair. |
| `examples/cake.json` | Приклад проєкту. |

## Потрібно
Python 3, `ffmpeg`, `pip install playwright pillow numpy` і Chromium для Playwright. Для «за людиною» ще `pip install rembg onnxruntime` (модель `u2net_human_seg` завантажується сама).

## Команди
```bash
python3 apply_pack.py project.json receipt project.json      # стиль «Чек»
python3 build_artifact.py project.json preview.mp4 editor_page.html [matte.webm]
python3 render.py project.json назва                          # -> out/назва_9x16.mp4, out/назва_4x5.mp4
python3 make_matte.py video.mp4 matte.webm 540 "2.0-4.5"      # вирізка людини на 2–4.5 с
```

Шрифти в `fonts/` і `fontlib/` поширюються за ліцензією SIL Open Font License 1.1 (https://openfontlicense.org).
