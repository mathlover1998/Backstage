# Backstage

Hát bài mình thích trước mặt mọi người mà không mất tự tin: **loa ngoài chỉ phát beat**,
**tai nghe phát guide có giọng gốc** — hai đường sync tuyệt đối.

## Nguyên tắc kiến trúc

Không bao giờ phát bản gốc trực tiếp ra tai nghe. Thay vào đó:

```
Loa      ← beat
Tai nghe ← beat + vocal đã align
```

`beat` ở hai dòng trên là **đúng một file**, nên sync được đảm bảo *by construction*,
bất kể beat đến từ đâu. Toàn bộ độ khó dồn về một chỗ duy nhất: align vocal lên beat,
làm offline, một lần cho mỗi cặp (bài, beat).

Hai nguồn beat:

| | Nguồn | Align |
|---|---|---|
| Option 1 | AI tách từ chính bản gốc (Demucs) | miễn phí — sample-aligned sẵn |
| Option 2 | Beat có sẵn / do người dùng cung cấp | chroma + DTW warp |

### Phương án phát (Phương án A)

Render ra **một file stereo**: `L = beat + vocal`, `R = beat`. Dùng jack chia đôi —
một nhánh vào tai nghe (lấy L), nhánh kia cắm aux vào loa (lấy R). Hai kênh nằm trong
cùng một buffer, cùng một clock, nên lệch bằng 0 tuyệt đối. Đổi lại: mono mỗi bên.

## Môi trường

Mọi thứ gói trong thư mục dự án. Python hệ thống (3.14) không bị đụng tới.

| | |
|---|---|
| Python | 3.11.17 (uv quản lý, ghim trong `.python-version`) |
| Tách | `demucs` 4.1.0 + `torch` 2.14.1 **+cpu** |
| Align | `librosa` 0.11 (chroma + `librosa.sequence.dtw`) |
| Audio IO | `soundfile` / `sphn`, `imageio-ffmpeg` (ffmpeg nằm trong venv) |
| Playback | `sounddevice` (PortAudio) |
| UI | PySide6 6.12 |

### Chạy

```powershell
# uv cai o C:\Users\<user>\.local\bin - them vao PATH neu shell chua thay
$env:Path = "$env:USERPROFILE\.local\bin;$env:Path"

uv sync --locked                         # dung lai moi truong tu uv.lock
uv run python scripts/smoke_test.py      # kiem tra + liet ke output device
```

### Dùng (Option 1)

```powershell
uv run backstage ui                            # cua so: chon file + slider guide gain
uv run backstage devices                       # xem output device nao dang co
uv run backstage prepare "D:\nhac\bai.mp3"     # tach + render + ghi manifest
uv run backstage play    "D:\nhac\bai.mp3" --guide 0.7 --device "Realtek"
```

`prepare` cache theo (fingerprint file, model) nên chạy lại là tức thì.
`play` mix trực tiếp từ stems chứ không phát `render.wav` — để `guide_gain`
còn đổi được lúc đang hát. `render.wav` là artifact mang đi máy khác.

Dùng `ui` nếu muốn **kéo slider giọng guide trong lúc đang hát** — CLI chỉ nhận
một giá trị cố định lúc khởi động.

**Đã kiểm chứng** trên `render.wav` sinh từ một lần tách thật:

```
max|R - mono(no_vocals)|   = 1.19e-07   (= 2^-23, dung san luong tu 24-bit)
max|(L-R) - mono(vocals)|  = 1.19e-07
lag cross-correlation      = 0 mau
```

Beat ở hai kênh triệt tiêu hoàn toàn, không có offset.

Các bước CI chạy (xem `.github/workflows/ci.yml`) — chạy được hết ở local:

```powershell
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
uv run python scripts/smoke_test.py --imports-only
```

### Vài quyết định đã chốt, kèm lý do

- **Không có `torchaudio`.** demucs 4.1.0 chỉ cần nó cho extra `train`; runtime dùng
  `sphn`. Thêm vào chỉ tạo ràng buộc ABI với torch — đã từng gây `WinError 127`.
- **`tool.uv.environments` giới hạn platform.** Lock universal của uv phủ cả macOS
  x86_64, nơi demucs ghim `torch<2.3`. Ràng buộc của Intel Mac kéo torch trên Windows
  xuống 2.2.2. Giới hạn còn win32 + linux x86_64 + darwin arm64 thì torch lên 2.14.
- **torch bản CPU.** Máy dev chỉ có Intel UHD 770, không CUDA. Tách một bài 4 phút mất
  khoảng 2–4 phút trên i7-13700 → mọi job engine **phải** chạy worker thread riêng có
  progress, không bao giờ block UI thread.

## Cấu trúc

```
src/backstage/
  manifest.py          # artifact contract - hop dong trung tam engine <-> player
  paths.py             # cache layout, key theo fingerprint
  engine/separate.py   # Demucs -> vocals.wav + no_vocals.wav
  engine/render.py     # -> render.wav stereo: L = guide, R = beat
  player/device.py     # liet ke / chon output device
  player/dual.py       # OutputStream 2 kenh, mix trong callback
  ui/app.py            # cua so PySide6
  cli.py               # ui | devices | prepare | play
scripts/
  smoke_test.py
cache/                 # stems + render + manifest (gitignored)
```

> Thư mục dự án vẫn tên `D:\Music Split App`. Đổi tên thư mục phải làm ngoài
> phiên làm việc (đóng editor → đổi tên → mở lại), vì nó là cwd và chứa `.venv`
> với đường dẫn tuyệt đối. Không ảnh hưởng gì tới code.
