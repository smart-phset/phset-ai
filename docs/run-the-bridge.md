# Run the bridge

How to run the AI on the farm laptop and connect it to the website or the Node backend.

```
phone / website --> Vercel (smartphset.vercel.app) --tunnel--> laptop: bridge.py :8000 --> models/best.pt
                    or the Node backend on the laptop ---------> bridge.py :8000
```

## 1. One-time setup

Needs Python 3.11 and Git.

```powershell
git clone git@github.com:menghoutishere-code/SmartPhset-AI.git
cd SmartPhset-AI
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If PowerShell refuses to run `Activate.ps1`, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

## 2. Start it

Pick a long random key and use the **same key** everywhere (bridge, Vercel, backend). Never commit it.

```powershell
.\.venv\Scripts\Activate.ps1
$env:BRIDGE_API_KEY = "<the key>"
python bridge.py --api-key $env:BRIDGE_API_KEY
```

It prints `SmartPhset bridge on http://0.0.0.0:8000/`. Loading the model takes a few seconds.

**Check it works:**
- Open `http://localhost:8000/?key=<the key>` and upload a photo from `evidence/demo/`.
- Or `curl -H "Authorization: Bearer <the key>" http://localhost:8000/status`.

Other devices on the same Wi-Fi can reach it at `http://<laptop-ip>:8000/`.

## 3. Connect the live website (bridge mode)

This gives real AI results on https://smartphset.vercel.app. Climate readings stay simulated in this mode.

1. **Start a tunnel** to port 8000, so Vercel can reach the laptop. With Cloudflare's free quick tunnel:
   ```powershell
   cloudflared tunnel --url http://localhost:8000
   ```
   It prints an address like `https://xyz.trycloudflare.com`. It changes every time the tunnel restarts.
2. **In Vercel** (project `smartphset` -> Settings -> Environment Variables), set:
   - `BACKEND_URL` = the tunnel address, no trailing slash
   - `BACKEND_MODE` = `bridge`
   - `API_KEY` = the same key as `BRIDGE_API_KEY`
3. **Redeploy** the website, so it picks up the new values.
4. **Test:** on the site, AI scan -> upload a bag photo. The "Demo data" tag disappears and the result comes from
   the laptop.

To go back to demo mode, clear `BACKEND_URL` in Vercel and redeploy.

## 4. Connect the Node backend (api mode)

The backend runs on the same laptop and calls the bridge directly; no tunnel is needed between them.

- **Call:** `POST http://127.0.0.1:8000/image?camera=<camera id>`, body = raw JPEG bytes,
  headers `Content-Type: image/jpeg` and `Authorization: Bearer <key>`.
- **Reply:** see [bridge-api.md](bridge-api.md).
- **Then the backend:** stores the photo, adds `id`, `level`, `time` and `file_url`, and answers the website in the
  shape of the website repo's `docs/api-contract.md`.
- **Level rule:** red at `max_contaminated_conf` 0.80 or more, amber at 0.40 to 0.79. `no_detection` and
  `camera_error` are grey "could not check", never healthy.

In this mode the tunnel points at the backend, and Vercel uses `BACKEND_MODE=api`.

## 5. On demo day

- Turn off sleep on the laptop and keep it plugged in.
- Start the bridge, then the tunnel, then check `/status` through the tunnel address before going on stage.
- Do not open the CSV logs in Excel while the bridge runs (Excel locks them). Open a copy.
- **Backup:** if the internet fails, the bridge's own page (`http://<laptop-ip>:8000/`) still works over the local
  Wi-Fi.

## Troubleshooting

| Problem | Fix |
|---|---|
| `401 unauthorized` | The key in the request does not match `--api-key` |
| `ModuleNotFoundError` | The venv is not active; run `.\.venv\Scripts\Activate.ps1` |
| Phone cannot reach `http://<laptop-ip>:8000` | Same Wi-Fi? Allow Python through Windows Firewall (private networks) |
| Website still shows "Demo data" | `BACKEND_URL` not set, or the site was not redeployed after setting it |
| Result is "no_detection" | No bag recognised: move closer (20-30 cm), more light, one bag face filling the frame |
| Port 8000 busy | `python bridge.py --port 8001 ...` and point the tunnel at 8001 |
