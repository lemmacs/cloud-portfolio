const API_URL = "https://onhwcq5ckh.execute-api.us-east-1.amazonaws.com/visitor-count";

async function getVisitorCount() {
    try {
        const response = await fetch(API_URL);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();

        document.getElementById("visitor-count").textContent =
            `👀 Visitors: ${data.count}`;

    } catch (error) {
        console.error("Visitor counter failed:", error);

        document.getElementById("visitor-count").textContent =
            "👀 Visitors: Unavailable";
    }
}

getVisitorCount();