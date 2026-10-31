const API_URL = "https://onhwcq5ckh.execute-api.us-east-1.amazonaws.com/visitor-count";

// Set this to true in your own browser to exclude your visits.
const EXCLUDE_MY_TRAFFIC_KEY = "portfolio-exclude-my-traffic";

function isExcludedBrowser(){
    return localStorage.getItem(EXCLUDE_MY_TRAFFIC_KEY) === "true";
}

async function getVisitorCount() {
    try{
        const url = new URL(API_URL);

        if(isExcludedBrowser()){
            url.searchParams.set("exclude", "1");
        }

        const response = await fetch(url);

        if(!response.ok){
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();

        document.getElementById("visitor-count").textContent =
            data.excluded
                ? `👀 Visitors: ${data.count} (your visit excluded)`
                : `👀 Visitors: ${data.count}`;
    }
    
    catch (error) {
        console.error("Visitor counter failed:", error);

        document.getElementById("visitor-count").textContent =
            "👀 Visitors: Unavailable";
    }
}

getVisitorCount();

const ANALYTICS_API_URL =
    "https://onhwcq5ckh.execute-api.us-east-1.amazonaws.com/analytics-event";

const analyticsLinks  = document.querySelectorAll(
    '[data-analytics-event]'
);

analyticsLinks.forEach((link) => {
    link.addEventListener("click", () => {
        if (isExcludedBrowser()) return;

        const eventRecord = {
            event_name: link.dataset.analyticsEvent
        };

        if (link.dataset.project) {
            eventRecord.project = link.dataset.project;
        }

        if (link.dataset.section) {
            eventRecord.section = link.dataset.section;
        }

        fetch(ANALYTICS_API_URL, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(eventRecord),
                keepalive: true
        }).catch((error) => {
            console.error("Analytics request failed:", error);
        });
    });
});
