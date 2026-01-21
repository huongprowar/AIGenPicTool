/**
 * Popup Script
 * Hiển thị token và xử lý các actions
 */

const statusEl = document.getElementById("status");
const tokenBox = document.getElementById("tokenBox");
const timestampEl = document.getElementById("timestamp");
const copyBtn = document.getElementById("copyBtn");
const refreshBtn = document.getElementById("refreshBtn");
const clearBtn = document.getElementById("clearBtn");
const copiedMsg = document.getElementById("copiedMsg");

// Load token khi mở popup
loadToken();

// Event listeners
copyBtn.addEventListener("click", copyToken);
refreshBtn.addEventListener("click", loadToken);
clearBtn.addEventListener("click", clearToken);

function loadToken() {
  chrome.runtime.sendMessage({ action: "getToken" }, (response) => {
    if (response && response.token) {
      displayToken(response.token, response.timestamp);
    } else {
      displayNoToken();
    }
  });
}

function displayToken(token, timestamp) {
  // Hiển thị token (rút gọn)
  const shortToken = token.substring(0, 50) + "..." + token.substring(token.length - 20);
  tokenBox.textContent = shortToken;
  tokenBox.classList.remove("empty");
  tokenBox.title = "Click Copy để lấy full token";

  // Lưu full token để copy
  tokenBox.dataset.fullToken = token;

  // Hiển thị timestamp
  const age = Date.now() - timestamp;
  const minutes = Math.floor(age / 60000);

  if (minutes < 1) {
    timestampEl.textContent = "Vừa lấy được";
  } else if (minutes < 60) {
    timestampEl.textContent = `Lấy ${minutes} phút trước`;
  } else {
    const hours = Math.floor(minutes / 60);
    timestampEl.textContent = `Lấy ${hours} giờ trước`;
  }

  // Cập nhật status
  if (minutes < 50) {
    setStatus("success", "✓", `Token hợp lệ (còn ~${50 - minutes} phút)`);
    copyBtn.disabled = false;
  } else {
    setStatus("warning", "⚠", "Token có thể đã hết hạn, hãy tạo request mới");
    copyBtn.disabled = false;
  }
}

function displayNoToken() {
  tokenBox.textContent = "Chưa có token - Hãy mở Google Labs ImageFX và tạo 1 ảnh";
  tokenBox.classList.add("empty");
  tokenBox.dataset.fullToken = "";
  timestampEl.textContent = "";
  copyBtn.disabled = true;
  setStatus("error", "✗", "Chưa có token");
}

function setStatus(type, icon, text) {
  statusEl.className = `status ${type}`;
  statusEl.innerHTML = `<span class="status-icon">${icon}</span><span class="status-text">${text}</span>`;
}

async function copyToken() {
  const token = tokenBox.dataset.fullToken;
  if (!token) return;

  try {
    await navigator.clipboard.writeText(token);

    // Hiển thị thông báo
    copiedMsg.style.display = "block";
    setTimeout(() => {
      copiedMsg.style.display = "none";
    }, 1500);

    // Đổi text button tạm thời
    copyBtn.textContent = "✓ Đã copy!";
    setTimeout(() => {
      copyBtn.textContent = "📋 Copy Token";
    }, 2000);
  } catch (err) {
    // Fallback cho trường hợp clipboard API không hoạt động
    const textarea = document.createElement("textarea");
    textarea.value = token;
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand("copy");
    document.body.removeChild(textarea);

    copiedMsg.style.display = "block";
    setTimeout(() => {
      copiedMsg.style.display = "none";
    }, 1500);
  }
}

function clearToken() {
  chrome.runtime.sendMessage({ action: "clearToken" }, (response) => {
    if (response && response.success) {
      displayNoToken();
    }
  });
}

// Auto-refresh mỗi 5 giây khi popup mở
setInterval(loadToken, 5000);
