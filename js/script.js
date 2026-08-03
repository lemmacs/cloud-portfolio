const API_URL = "https://onhwcq5ckh.execute-api.us-east-1.amazonaws.com/visitor-count";

async function getVisitorCount() {
    try {
        const response = await fetch(API_URL);
        const result = await response.json();

        // Lambda returns the JSON as a string in "body"
        const data = JSON.parse(result.body);

        document.getElementById("visitor-count").textContent =
            `👀 Visitors: ${data.count}`;
    } catch (error) {
        console.error("Visitor counter failed:", error);

        document.getElementById("visitor-count").textContent =
            "👀 Visitors: Unavailable";
    }
}

getVisitorCount();