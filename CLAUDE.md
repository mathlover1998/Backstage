# Backstage

Giúp người không phải ca sĩ dám hát trước mặt mọi người: **loa ngoài chỉ phát beat**,
**tai nghe phát guide có giọng gốc**, hai đường sync tuyệt đối. Người hát có chỗ dựa,
khán giả chỉ nghe beat + giọng thật của họ.

## Bất biến kiến trúc — đừng phá

**Không bao giờ phát bản gốc trực tiếp ra tai nghe.** Luôn là:

```
Loa      ← beat
Tai nghe ← beat + vocal đã align
```

`beat` ở hai dòng trên phải là **đúng một file**. Nhờ vậy sync được đảm bảo
*by construction*, không phải canh ở runtime. Mọi độ khó dồn về một chỗ duy nhất:
align vocal lên beat, làm **offline**, một lần cho mỗi cặp (bài, beat).

Nếu có lúc nào thấy mình đang viết code đồng bộ hai stream lúc phát, nghĩa là đã đi sai:
quay lại render một file stereo `L = beat + vocal`, `R = beat`.

Hai nguồn beat:

| | Nguồn | Align |
|---|---|---|
| Option 1 | AI tách từ chính bản gốc (Demucs) | miễn phí — sample-aligned sẵn |
| Option 2 | Beat có sẵn / người dùng cung cấp | chroma + DTW warp |

Với Option 2: **warp vocal, không warp beat.** Beat là thứ khán giả nghe, phải giữ
nguyên không artifact; vocal chỉ là guide trong tai, chịu được time-stretch nhẹ.

## Hai quyết định dependency — đừng "dọn dẹp"

Cả hai trông như thiếu sót nhưng đều có chủ ý. Lý do đầy đủ trong `README.md`.

1. **`torchaudio` không có trong deps.** demucs 4.1.0 chỉ cần nó cho extra `train`;
   runtime dùng `sphn`. Thêm vào chỉ tạo ràng buộc ABI với torch — đã từng gây
   `OSError: [WinError 127]` khi import.
2. **`tool.uv.environments` giới hạn platform.** Lock universal của uv phủ cả macOS
   x86_64, nơi demucs ghim `torch<2.3`; ràng buộc đó kéo torch trên Windows xuống
   2.2.2. Gỡ giới hạn này ra là lặp lại đúng lỗi trên.

## Môi trường

Python 3.11.17 do `uv` quản lý, biệt lập hoàn toàn với Python 3.14 của hệ thống.
`uv` nằm ở `C:\Users\<user>\.local\bin` — shell có thể chưa có trong PATH:

```powershell
$env:Path = "$env:USERPROFILE\.local\bin;$env:Path"

uv sync --locked
uv run ruff check . ; uv run ruff format --check . ; uv run pytest -q
uv run python scripts/smoke_test.py      # + liệt kê audio output device
```

## Ràng buộc máy dev

Intel UHD 770, **không có CUDA** → torch bản `+cpu`, tách một bài 4 phút mất khoảng
**2–4 phút** trên i7-13700. Hệ quả bắt buộc: mọi job engine phải chạy **worker thread
riêng có progress**, không bao giờ block UI thread. Thiết kế việc này vào từ đầu,
đừng chắp sau.

## Trạng thái hiện tại

**Option 1 chạy được end-to-end.**

```
src/msa/manifest.py          artifact contract - hợp đồng engine <-> player
src/msa/paths.py             cache layout, fingerprint theo nội dung file
src/msa/engine/separate.py   Demucs -> vocals.wav + no_vocals.wav (cache theo fp+model)
src/msa/engine/render.py     -> render.wav stereo: L = guide, R = beat
src/msa/player/device.py     liệt kê / chọn output device
src/msa/player/dual.py       OutputStream 2 kênh, mix trong callback
src/msa/cli.py               msa devices | prepare | play
```

**Chưa tồn tại** (chưa phải stub, là chưa có file): `engine/align.py`, `engine/score.py`
(cả hai cho Option 2), `jobs.py`, `ui/app.py`.

### Kiểm chứng đã làm trên output thật của Demucs

Trên `render.wav` sinh từ một lần tách thật:

```
max|R - mono(no_vocals)|    = 1.19e-07   (= 2^-23, đúng sàn lượng tử 24-bit)
max|(L-R) - mono(vocals)|   = 1.19e-07
lag cross-correlation       = 0 mẫu
```

Tức beat ở hai kênh triệt tiêu hoàn toàn — sai số duy nhất là lượng tử hóa 24-bit,
không có offset. Test `test_render.py::test_beat_cancels_exactly_between_channels`
giữ tính chất này; **đừng xoá nó**, nó là lời hứa cốt lõi của sản phẩm dưới dạng
một phép trừ.

### Chưa làm / chưa biết

- **Chưa phát thử ra thiết bị thật.** Toàn bộ kiểm chứng ở trên là trên file. Chưa
  ai cắm jack chia đôi và nghe, nên chưa biết `blocksize=1024` có đủ tránh dropout
  hay chưa.
- **Chưa thử retask jack Realtek** để lấy hai cặp stereo độc lập (Phương án B,
  xem README). Realtek trên máy dev báo 8 kênh nên khả năng có.

## Lưu ý

- Package Python vẫn tên `msa`, chưa đổi theo tên dự án `Backstage`.
- **Không commit file audio.** `.gitignore` đã chặn; đừng nới ra.
- Comment và docstring trong code viết **tiếng Việt không dấu** (tránh lỗi encoding trên
  Windows console); tài liệu `.md` thì có dấu bình thường.
