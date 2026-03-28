const form = document.getElementById("session-form");
const statusDiv = document.getElementById("session-status");
const sessionPanel = document.getElementById("session-panel");
const summaryPanel = document.getElementById("summary-panel");
const summaryText = document.getElementById("summary-text");
const video = document.getElementById("video");
const focusStatus = document.getElementById("focus-status");
const timerDisplay = document.getElementById("timer");
const endButton = document.getElementById("end-session-button");
const alertSound = document.getElementById("alert-sound");
const liveStats = document.getElementById("live-stats");
const focusBanner = document.getElementById("focus-banner");
const saveDefaultsCheckbox = document.getElementById("save-defaults");

const DEFAULTS_KEY = "focusSentryDefaults";

let sessionId = null;
let frameIntervalId = null;
let countdownIntervalId = null;
let mediaStream = null;

let currentState = "unknown";
let lastStateChangeMs = null;
let unfocusedStartMs = null;

let alertTriggeredThisBreak = false;
let inAlertState = false;

let focusedMsTotal = 0;
let unfocusedMsTotal = 0;
let breaksCount = 0;

let focusedRunFrames = 0;
let unfocusedRunFrames = 0;

const FOCUS_DEBOUNCE_FRAMES = 2;
const UNFOCUS_DEBOUNCE_FRAMES = 3;

let UNFOCUSED_THRESHOLD_MS = 2500;
let alertMode = "popup";

let bannerTimeoutId = null;
const BANNER_DISPLAY_MS = 3000;

/* 📊 CHART */
let focusChart = null;

function initChart() {
    const ctx = document.getElementById("focusChart");
    if (!ctx) return;

    focusChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Focus Score',
                data: [],
                borderColor: '#22c55e',
                borderWidth: 2,
                tension: 0.3
            }]
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: { y: { min: 0, max: 100 } }
        }
    });
}

function updateChart(isFocused) {
    if (!focusChart) return;

    const value = isFocused ? 100 : 0;
    const time = new Date().toLocaleTimeString();

    focusChart.data.labels.push(time);
    focusChart.data.datasets[0].data.push(value);

    if (focusChart.data.labels.length > 20) {
        focusChart.data.labels.shift();
        focusChart.data.datasets[0].data.shift();
    }

    focusChart.update();
}

/* CAMERA */
async function startCamera() {
    mediaStream = await navigator.mediaDevices.getUserMedia({
        video: true,
        audio: false,
    });
    video.srcObject = mediaStream;
}

/* START SESSION */
form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const durationMinutes = Number(form.duration.value);
    const email = form.email.value;
    const phone = form.phone.value;
    const alertThresholdSeconds = Number(form.alert_threshold.value);
    const mode = form.alert_mode.value;

    const sendEmail = form.send_email.checked;
    const sendSms = form.send_sms.checked;

    const formData = new FormData();
    formData.append("duration_minutes", durationMinutes);
    formData.append("alert_threshold", alertThresholdSeconds);
    formData.append("alert_mode", mode);

    if (email) formData.append("email", email);
    if (phone) formData.append("phone", phone);
    if (sendEmail) formData.append("send_email_flag", "true");
    if (sendSms) formData.append("send_sms_flag", "true");

    statusDiv.textContent = "Starting session...";

    try {
        const res = await fetch("/start-session", {
            method: "POST",
            body: formData,
        });

        const data = await res.json();

        sessionId = data.session_id;
        UNFOCUSED_THRESHOLD_MS = data.alert_threshold_ms;
        alertMode = data.alert_mode;

        statusDiv.textContent = "Session started.";
        sessionPanel.style.display = "block";
        summaryPanel.style.display = "none";

        initChart(); // ✅ graph start

        resetTracking();
        await startCamera();
        startFrameLoop();
        startCountdown(durationMinutes);

    } catch (err) {
        console.error(err);
        statusDiv.textContent = "Error starting session.";
    }
});

/* FRAME LOOP */
function startFrameLoop() {
    frameIntervalId = setInterval(sendFrame, 300);
}

async function sendFrame() {
    if (!sessionId || !video.srcObject) return;

    const blob = await captureFrameBlob();
    if (!blob) return;

    const formData = new FormData();
    formData.append("session_id", sessionId);
    formData.append("frame", blob, "frame.jpg");

    const res = await fetch("/frame", {
        method: "POST",
        body: formData,
    });

    const data = await res.json();
    handleFocusState(Boolean(data.focused));
}

/* CAPTURE FRAME */
function captureFrameBlob() {
    return new Promise((resolve) => {
        const canvas = document.createElement("canvas");
        canvas.width = 320;
        canvas.height = 240;

        const ctx = canvas.getContext("2d");
        ctx.drawImage(video, 0, 0);

        canvas.toBlob(resolve, "image/jpeg", 1.0);
    });
}

/* CORE LOGIC */
function handleFocusState(isFocusedRaw) {
    const now = Date.now();

    if (lastStateChangeMs === null) {
        lastStateChangeMs = now;
    }

    const delta = now - lastStateChangeMs;

    if (currentState === "focused") focusedMsTotal += delta;
    else if (currentState === "unfocused") unfocusedMsTotal += delta;

    if (isFocusedRaw) {
        focusedRunFrames++;
        unfocusedRunFrames = 0;
    } else {
        unfocusedRunFrames++;
        focusedRunFrames = 0;
    }

    let isFocused;
    if (currentState === "focused") {
        isFocused = unfocusedRunFrames < UNFOCUS_DEBOUNCE_FRAMES;
    } else {
        isFocused = focusedRunFrames >= FOCUS_DEBOUNCE_FRAMES;
    }

    if (isFocused) {
        currentState = "focused";
        focusStatus.textContent = "Focus state: focused ✅";

        video.classList.add("focused");
        video.classList.remove("unfocused");

    } else {
        currentState = "unfocused";
        focusStatus.textContent = "Focus state: unfocused ❌";

        video.classList.add("unfocused");
        video.classList.remove("focused");
    }

    lastStateChangeMs = now;

    updateLiveStats();
    updateChart(isFocused); // 📊 update graph
}

/* LIVE STATS */
function updateLiveStats() {
    const total = focusedMsTotal + unfocusedMsTotal;
    const percent = total > 0 ? Math.round((focusedMsTotal / total) * 100) : 0;

    liveStats.textContent = `Focused: ${percent}% , breaks: ${breaksCount}`;
}

/* TIMER */
function startCountdown(minutes) {
    const endTime = Date.now() + minutes * 60000;

    countdownIntervalId = setInterval(() => {
        const remaining = endTime - Date.now();

        if (remaining <= 0) {
            clearInterval(countdownIntervalId);
            endSessionNow(false);
            return;
        }

        const sec = Math.floor(remaining / 1000);
        timerDisplay.textContent =
            "Time left: " +
            Math.floor(sec / 60) +
            ":" +
            String(sec % 60).padStart(2, "0");
    }, 1000);
}

/* END SESSION */
function endSessionNow() {
    clearInterval(frameIntervalId);
    clearInterval(countdownIntervalId);

    if (mediaStream) {
        mediaStream.getTracks().forEach(t => t.stop());
    }

    const total = focusedMsTotal + unfocusedMsTotal;
    const percent = total > 0 ? Math.round((focusedMsTotal / total) * 100) : 0;

    summaryText.textContent = `Focus: ${percent}%`;
    summaryPanel.style.display = "block";
}

/* LOAD DEFAULTS */
loadDefaultsFromStorage();