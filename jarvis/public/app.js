// SVGs Rings calculations
const CIRCUMFERENCE = 2 * Math.PI * 50; // Radius = 50

function setProgress(circleId, pct) {
    const circle = document.getElementById(circleId);
    if (!circle) return;
    const offset = CIRCUMFERENCE - (pct / 100) * CIRCUMFERENCE;
    circle.style.strokeDasharray = `${CIRCUMFERENCE} ${CIRCUMFERENCE}`;
    circle.style.strokeDashoffset = offset;
}

// Format Uptime
function formatUptime(seconds) {
    if (isNaN(seconds) || seconds === null) return "00:00:00";
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    return [
        h.toString().padStart(2, '0'),
        m.toString().padStart(2, '0'),
        s.toString().padStart(2, '0')
    ].join(':');
}

// Update clock
function updateClock() {
    const timeEl = document.getElementById('sysTime');
    if (timeEl) {
        timeEl.textContent = new Date().toLocaleTimeString();
    }
}
setInterval(updateClock, 1000);
updateClock();

// Fetch System Metrics
async function fetchMetrics() {
    try {
        const response = await fetch('/api/metrics');
        if (!response.ok) throw new Error('Network response was not ok');
        const data = await response.json();

        // Update CPU
        document.getElementById('cpuValue').textContent = `${data.cpu}%`;
        setProgress('cpuRing', data.cpu);

        // Update RAM
        document.getElementById('ramValue').textContent = `${data.ram.pct}%`;
        setProgress('ramRing', data.ram.pct);
        
        const totalGB = Math.round((data.ram.total / 1073741824) * 100) / 100;
        const usedGB = Math.round((data.ram.used / 1073741824) * 100) / 100;
        document.getElementById('ramDetails').textContent = `RAM: ${usedGB} GB / ${totalGB} GB`;

        // Update Network
        let rxTotal = 0.0;
        let txTotal = 0.0;
        if (data.network && data.network.length > 0) {
            data.network.forEach(n => {
                rxTotal += n.rx;
                txTotal += n.tx;
            });
        }
        document.getElementById('dlSpeed').textContent = `${rxTotal.toFixed(2)} Mbps`;
        document.getElementById('ulSpeed').textContent = `${txTotal.toFixed(2)} Mbps`;

        // Update Uptime
        document.getElementById('uptime').textContent = `Uptime: ${formatUptime(data.uptime)}`;
    } catch (e) {
        console.error('Error fetching metrics:', e);
    }
}
setInterval(fetchMetrics, 1000);
fetchMetrics();

// Fetch Repository Build Status
async function fetchBuildStatus() {
    try {
        const response = await fetch('/api/build');
        if (!response.ok) throw new Error('Build fetch error');
        const data = await response.json();

        document.getElementById('buildRepo').textContent = data.repo || "NEPCS-HR-ERP";
        document.getElementById('buildFiles').textContent = data.files || "0";
        document.getElementById('buildBranch').textContent = data.branch || "main";
        
        const statusEl = document.getElementById('buildStatus');
        statusEl.textContent = data.status || "CLEAN";
        if (data.status === "MODIFIED") {
            statusEl.className = "value cyan-text";
        } else {
            statusEl.className = "value green-text";
        }
    } catch (e) {
        console.error('Error fetching build status:', e);
    }
}
setInterval(fetchBuildStatus, 5000);
fetchBuildStatus();

// Fetch Social Posts
async function fetchSocialFeed() {
    try {
        const response = await fetch('/api/posts');
        if (!response.ok) throw new Error('Posts fetch error');
        const posts = await response.json();
        const feedEl = document.getElementById('socialFeed');

        if (!posts || posts.length === 0) {
            feedEl.innerHTML = '<div class="empty-feed">No published updates yet.</div>';
            return;
        }

        feedEl.innerHTML = posts.map(post => {
            const timeStr = new Date(post.timestamp).toLocaleTimeString();
            return `
                <div class="feed-item">
                    <div class="item-header">
                        <span class="tag ${post.platform}">${post.platform}</span>
                        <span class="time">${timeStr}</span>
                    </div>
                    <div class="content">${post.content}</div>
                </div>
            `;
        }).join('');
    } catch (e) {
        console.error('Error fetching social feed:', e);
    }
}
setInterval(fetchSocialFeed, 5000);
fetchSocialFeed();

// Handle Social Form Submit
const postForm = document.getElementById('postForm');
if (postForm) {
    postForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        
        const content = document.getElementById('postContent').value.trim();
        const platform = document.getElementById('postPlatform').value;
        
        if (!content) return;

        try {
            const response = await fetch('/api/posts', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ content, platform })
            });

            if (response.ok) {
                document.getElementById('postContent').value = '';
                fetchSocialFeed();
            } else {
                console.error('Failed to post');
            }
        } catch (e) {
            console.error('Error submitting post:', e);
        }
    });
}
