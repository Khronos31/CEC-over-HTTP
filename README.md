# CEC-over-HTTP

A lightweight daemon that exposes your Raspberry Pi's hardware CEC capabilities as a simple, zero-latency HTTP REST API.

Raspberry PiのハードウェアCEC機能を、シンプルで遅延ゼロのHTTP REST APIとして公開する軽量デーモンです。Home Assistantなどのスマートホームハブから、ネットワーク経由でテレビやAVアンプを完全に支配（制御）するために設計されています。

---

## 🚀 Features (特徴)

1. **Zero-Latency Execution (遅延ゼロの即時実行)**
   - 起動時に `libcec` を初期化し、HDMIネットワークとの接続を常時保持（Keep-Alive）します。
   - 毎回 `cec-client` コマンドを起動するSSH方式のような数秒のオーバーヘッドがなく、HTTPリクエストを受け取った瞬間にミリ秒単位でCECコマンドを発射します。
2. **No MQTT Broker Required (MQTT不要)**
   - 複雑なMQTTブローカーの構築やトピックの管理は不要です。シンプルなHTTP GET/POSTリクエストだけで動作します。
3. **Perfect for Home Assistant (HAとの完璧な親和性)**
   - HAの `rest_command` と組み合わせることで、ネイティブなサービス呼び出しと同等のUXを実現します。
4. **Raw Command Support (生コマンドの直接送信)**
   - `1F:82:10:00` のような16進数のRawコマンドをURLパラメータで直接流し込めるため、メーカー独自の隠しコマンドや複雑なルーティングも自由自在です。

---

## 🛠️ Requirements (必須環境)

- **Hardware:** Raspberry Pi (Zero, 3, 4, 5 等) ※HDMI端子がテレビやAVアンプに接続されていること
- **OS:** Raspberry Pi OS (Debianベース)
- **Software:** Python 3.x, `libcec`, `aiohttp`

---

## 📦 Installation (インストールと起動)

### 1. 依存パッケージのインストール
Raspberry Pi上で、CECを制御するためのライブラリとPythonの非同期Webサーバーモジュールをインストールします。

```bash
sudo apt update
sudo apt install cec-utils python3-cec python3-aiohttp
```
*(※ `python3-cec` をaptでインストールすることで、面倒なC++ライブラリのビルドを回避できます)*

### 2. スクリプトの配置
このリポジトリをクローンし、ディレクトリに移動します。

```bash
git clone https://github.com/Khronos31/CEC-over-HTTP.git
cd CEC-over-HTTP
```

### 3. デーモンの起動テスト
以下のコマンドでサーバーを起動します（デフォルトポート: 8080）。

```bash
python3 cec_daemon.py
```
`======== Running on http://0.0.0.0:8080 ========` と表示されれば成功です。

---

## 📡 API Endpoints (API仕様)

ブラウザや `curl` コマンドから、Raspberry PiのIPアドレス（例: `192.168.1.100`）に向けてリクエストを送信します。

### 1. Rawコマンドの送信 (Send Raw Command)
任意の16進数CECコマンドを送信します。
- **URL:** `GET /tx?cmd=<HEX_COMMAND>`
- **Example:** `http://192.168.1.100:8080/tx?cmd=1F:82:10:00` (Active Source Broadcast)

### 2. テレビの電源ON (Power On TV)
- **URL:** `GET /power_on`
- **Example:** `http://192.168.1.100:8080/power_on`

### 3. テレビの電源OFF (Standby TV)
- **URL:** `GET /standby`
- **Example:** `http://192.168.1.100:8080/standby`

---

## 🏠 Home Assistant Integration (HAとの連携)

Home Assistantの `configuration.yaml` に `rest_command` を定義するだけで、HAから遅延ゼロでCECを撃ち込めるようになります。

```yaml
# configuration.yaml
rest_command:
  # 任意のRawコマンドを送信する大砲
  cec_living_tx:
    url: "http://192.168.1.100:8080/tx?cmd={{ cmd }}"
    method: GET

  # テレビの電源ON/OFFショートカット
  cec_living_tv_on:
    url: "http://192.168.1.100:8080/power_on"
    method: GET
  cec_living_tv_off:
    url: "http://192.168.1.100:8080/standby"
    method: GET
```

### オートメーションやスクリプトでの使用例
```yaml
action:
  - service: rest_command.cec_living_tx
    data:
      cmd: "0F:82:10:00" # HDMI 1へ入力切替
```

---

## ⚙️ Systemd Service (自動起動の設定)

Raspberry Piの再起動時に自動的にデーモンを立ち上げるための設定です。

1. `cec-daemon.service` を `/etc/systemd/system/` にコピーします。
   ```bash
   sudo cp systemd/cec-daemon.service /etc/systemd/system/
   ```
2. サービスを有効化し、起動します。
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable cec-daemon
   sudo systemctl start cec-daemon
   ```

---

## License
MIT License
