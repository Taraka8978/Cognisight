// sessionsData is injected by the template as a global array of session dicts

let chartInstance = null;

const rangeLabelEl = document.getElementById("range-label");
const avgFocusEl = document.getElementById("avg-focus");
const bestSessionEl = document.getElementById("best-session");
const filterButtons = document.querySelectorAll(".history-filter-button");

function parseDate(isoString) {
    if (!isoString) {
        return null;
    }
    const d = new Date(isoString);
    if (isNaN(d.getTime())) {
        return null;
    }
    return d;
}

function formatDateShort(isoString) {
    const d = parseDate(isoString);
    if (!d) {
        return isoString || "";
    }
    const year = d.getUTCFullYear();
    const month = String(d.getUTCMonth() + 1).padStart(2, "0");
    const day = String(d.getUTCDate()).padStart(2, "0");
    return year + "-" + month + "-" + day;
}

function filterSessions(rangeKey) {
    if (!Array.isArray(sessionsData)) {
        return [];
    }

    if (rangeKey === "all") {
        return sessionsData.slice();
    }

    const now = new Date();
    const days = rangeKey === "7" ? 7 : 30;
    const cutoffMs = now.getTime() - days * 24 * 60 * 60 * 1000;

    return sessionsData.filter((s) => {
        const d = parseDate(s.created_at);
        if (!d) {
            return false;
        }
        return d.getTime() >= cutoffMs;
    });
}

function computeStats(filtered) {
    const withFocus = filtered.filter(
        (s) =>
            typeof s.focus_percent === "number" &&
            !isNaN(s.focus_percent)
    );

    if (withFocus.length === 0) {
        return {
            avgFocus: null,
            best: null,
        };
    }

    let sum = 0;
    let best = withFocus[0];

    withFocus.forEach((s) => {
        sum += s.focus_percent;
        if (s.focus_percent > best.focus_percent) {
            best = s;
        }
    });

    const avgFocus = Math.round(sum / withFocus.length);

    return {
        avgFocus,
        best,
    };
}

function updateSummary(rangeKey, filtered) {
    if (!rangeLabelEl || !avgFocusEl || !bestSessionEl) {
        return;
    }

    let rangeText = "all loaded sessions";
    if (rangeKey === "7") {
        rangeText = "last 7 days";
    } else if (rangeKey === "30") {
        rangeText = "last 30 days";
    }

    if (filtered.length === 0) {
        rangeLabelEl.textContent =
            "Showing stats for: " + rangeText + " (no sessions in this range)";
        avgFocusEl.textContent = "Average focus: n/a";
        bestSessionEl.textContent = "Best session: n/a";
        return;
    }

    const stats = computeStats(filtered);

    rangeLabelEl.textContent =
        "Showing stats for: " +
        rangeText +
        " (" +
        filtered.length +
        " sessions)";

    if (stats.avgFocus === null) {
        avgFocusEl.textContent = "Average focus: n/a";
    } else {
        avgFocusEl.textContent =
            "Average focus: " + stats.avgFocus + " percent";
    }

    if (!stats.best) {
        bestSessionEl.textContent = "Best session: n/a";
    } else {
        const d = formatDateShort(stats.best.created_at);
        const dur = stats.best.duration_minutes || "?";
        const fp = stats.best.focus_percent;
        bestSessionEl.textContent =
            "Best session: " +
            fp +
            " percent on " +
            d +
            " (duration " +
            dur +
            " min)";
    }
}

function buildChart(filtered) {
    const canvas = document.getElementById("focusChart");
    if (!canvas) {
        return;
    }

    const ctx = canvas.getContext("2d");

    if (chartInstance) {
        chartInstance.destroy();
        chartInstance = null;
    }

    if (!filtered || filtered.length === 0) {
        // nothing to chart
        chartInstance = new Chart(ctx, {
            type: "line",
            data: {
                labels: [],
                datasets: [
                    {
                        label: "Focus percent",
                        data: [],
                        fill: false,
                    },
                ],
            },
            options: {
                responsive: true,
            },
        });
        return;
    }

    // oldest to newest for chart
    const ordered = filtered.slice().sort((a, b) => {
        const da = parseDate(a.created_at);
        const db = parseDate(b.created_at);
        if (!da && !db) return 0;
        if (!da) return -1;
        if (!db) return 1;
        return da.getTime() - db.getTime();
    });

    const labels = [];
    const values = [];
    const metaInfo = [];

    ordered.forEach((s, index) => {
        labels.push(index + 1);
        const fp =
            typeof s.focus_percent === "number" && !isNaN(s.focus_percent)
                ? s.focus_percent
                : 0;
        values.push(fp);
        metaInfo.push({
            date: formatDateShort(s.created_at),
            focus_percent: fp,
            duration_minutes: s.duration_minutes || null,
        });
    });

    chartInstance = new Chart(ctx, {
        type: "line",
        data: {
            labels: labels,
            datasets: [
                {
                    label: "Focus percent",
                    data: values,
                    fill: false,
                },
            ],
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    min: 0,
                    max: 100,
                    title: {
                        display: true,
                        text: "Focus percent",
                    },
                },
                x: {
                    title: {
                        display: true,
                        text: "Session index (oldest to newest)",
                    },
                },
            },
            plugins: {
                tooltip: {
                    callbacks: {
                        label: function (context) {
                            const index = context.dataIndex;
                            const meta = metaInfo[index];
                            if (!meta) {
                                return "Focus: " + context.parsed.y + " percent";
                            }
                            const durationText =
                                meta.duration_minutes !== null
                                    ? ", " + meta.duration_minutes + " min"
                                    : "";
                            return (
                                "Session on " +
                                meta.date +
                                ": " +
                                meta.focus_percent +
                                " percent" +
                                durationText
                            );
                        },
                    },
                },
            },
        },
    });
}

function applyRange(rangeKey) {
    const filtered = filterSessions(rangeKey);
    updateSummary(rangeKey, filtered);
    buildChart(filtered);
}

function wireFilterButtons() {
    if (!filterButtons || filterButtons.length === 0) {
        return;
    }

    filterButtons.forEach((btn) => {
        btn.addEventListener("click", () => {
            const rangeKey = btn.getAttribute("data-range") || "all";

            filterButtons.forEach((b) =>
                b.classList.remove("history-filter-active")
            );
            btn.classList.add("history-filter-active");

            applyRange(rangeKey);
        });
    });
}

if (typeof sessionsData !== "undefined" && sessionsData.length > 0) {
    wireFilterButtons();
    applyRange("all");
}