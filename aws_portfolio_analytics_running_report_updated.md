# AWS Portfolio Analytics --- Running Project Report & Study Guide

**Last updated:** November 06, 2026\
**Status:** In progress --- baseline and visitor filtering
implemented; persistent daily analytics collection and aggregation implemented and tested. PowerBI reporting pipeline remains in development.

> This is a living implementation log, architecture reference, and
> interview study guide. Update it after each meaningful implementation
> and test. Keep completed, tested, and planned work clearly separated.

## 1. Project goal

Extend the AWS-hosted software engineering portfolio into a
cost-conscious analytics project that tracks project/demo clicks,
section/button interactions, A/B test variants, and broad traffic
geography where feasible without storing raw IP addresses. Filter
obvious crawlers and the owner's own visits. Build a dashboard and
compare analytics value against incremental AWS cost.

The project has expanded from basic visitor counting into a lightweight website analytics system. The goal is to collect aggregated engagement metrics, understand how visitors interact with portfolio sections and project links, and eventually use those insights to guide improvements to the portfolio's content and user experience. 
The Analytics system prioritizes privacy and low operating costs by storing daily aggregated counts rather than individual visitor or click records. Microsoft Power BI has been selected as the primary reporting and visualization platform.

### Principles

-   Reuse existing AWS services where sensible and estimate costs before
    creating resources.
-   Do not store raw IP addresses, names, email addresses, credentials,
    or unnecessary personal data in analytics events.
-   Distinguish requests, visits, sessions, and estimated unique
    browsers. None automatically equals a unique human.
-   Test each small change before proceeding.
-   Preserve the original counter as a historical baseline.
-   Keep AWS WAF enabled unless a deliberate, documented review changes
    that decision.
-   Use only measured results for resume metrics.

## 2. Project architecture

``` text
GitHub repository
  -> GitHub Actions deployment
  -> Amazon S3 (static files)
  -> Amazon CloudFront (delivery/cache)
  -> Visitor browser
  -> API Gateway HTTP API (GET /visitor-count)
  -> AWS Lambda (portfolio-visitor-counter)
  -> DynamoDB (portfolio-visitors)
```
### 2.5 Current Analytics Architecture

The analytics system collect project-link clicks and navigation-section clicks through frontend JavaScript. Events are sent to a dedicated API Gateway endpoint, processed by a Lambda function, and stored as daily aggregate records in DynamoDB.

``` text
  -> Portfolio Website
  -> JavaScript Event Tracking
  -> API Gateway
    -> POST /analytics-event
  -> Lambda
    -> portfolio-analytics-collector
  -> DynamoDB
    -> portfolio-analytics-daily
```

A separate Lambda function retrieves the aggregated records and generates a JSON summary for reporting.

``` text
  -> DynamoDB
    -> portfolio-analytics-daily
  -> Lambda
    -> portfolio-analytics-dashboard
  -> JSON Analytics Summary
```

### Planned Reporting Architecture

This next phase will introduce an S3 export and Amazon Athena to make the aggregated analytics data accessible to Microsoft Power BI.

``` text
  -> DynamoDB
  -> S3 Export
  -> Amazon Athena
  -> Microsoft Power BI
  -> Analytics Dashboard
```


### Known resources

  -----------------------------------------------------------------------
  Resource                            Value / purpose
  ----------------------------------- -----------------------------------
  Region                              `us-east-1` (N. Virginia)

  S3 bucket                           `christian-lemma-portfolio-2026`

  API                                 API Gateway HTTP API,
                                      `GET /visitor-count`

  Lambda                              `portfolio-visitor-counter`

  DynamoDB table                      `portfolio-visitors`

  Counter key                         `id = visitor-count`

  Counter attribute                   `visitCount`

  Front-end files                     `index.html`, `css/style.css`,
                                      `js/script.js`

  Deployment                          GitHub Actions on push to `main`;
                                      syncs site files to S3 and
                                      invalidates CloudFront
  -----------------------------------------------------------------------

**Public documentation hygiene:** do not publish AWS account IDs,
internal distribution IDs, IAM details, sampled source IPs, credentials,
or secrets. Keep public docs focused on architecture and decisions.

## 3. Baseline

### Visitor count

  ------------------------------------------------------------------------
  Measurement                                  Value Meaning
  --------------------- ---------------------------- ---------------------
  Original pre-filter                        **395** Historical,
  snapshot                                           unfiltered counter
                                                     value

  Current count at last                      **413** DynamoDB value after
  verification                                       development/testing
                                                     activity

  Difference                                  **18** Increments since the
                                                     original snapshot;
                                                     may include testing,
                                                     automation, and real
                                                     visitors
  ------------------------------------------------------------------------

The 18-increment difference is not a verified unique-visitor count. Some
endpoint requests during implementation were counted before the
self-traffic exclusion was fully deployed.

The Lambda bot test was invoked directly in the Lambda console after the
count reached 413. The response returned `excluded: true`; DynamoDB was
checked afterward and `visitCount` remained 413.

### Analytics Implementation Baseline

  The new analytics system was developed using test events to validate event collection, DynamoDB aggregatio, and dashboard processing. These events are not representative of genuine visitor enngagement and should not be used as a clean baseline for portfolio traffic.
  The original visitor counter and historical AWS cost figures remain separate from the new analytics metrics.

### AWS cost baseline (from reviewed billing export)

  Period                                               Reported total
  ------------------------------ ------------------------------------
  July 2026                                      Approximately \$2.80
  August 2026                                    Approximately \$8.00
  September 2026                                 Approximately \$8.00
  October 2026, at review time     Approximately \$7.01 month-to-date

These are historical values, not a final October bill or guaranteed
future price. AWS WAF was the main observed cost in the reviewed export.
S3, API Gateway, DynamoDB, Lambda, and CloudFront were negligible in
that export at that time. Check current billing and pricing before
making forecasts.

### WAF decision

**Decision: retain AWS WAF Core protections enabled.**

Existing managed rule groups: -
`AWS-AWSManagedRulesAmazonIpReputationList` -
`AWS-AWSManagedRulesCommonRuleSet` -
`AWS-AWSManagedRulesKnownBadInputsRuleSet`

Advanced DDoS protection was not enabled during the review. Sampled
static-asset requests were allowed; samples are not a complete traffic
log or proof that every request is safe. The project accepts the
observed WAF cost as an additional security layer and will monitor WAF
and total AWS spending.

## 4. Implementation log

### Phase 0 --- Existing visitor counter

The original Lambda incremented the DynamoDB counter on each request
using an atomic update:

``` python
table.update_item(
    Key={"id": "visitor-count"},
    UpdateExpression="ADD visitCount :inc",
    ExpressionAttributeValues={":inc": 1},
    ReturnValues="UPDATED_NEW"
)
```

There was initially no filter for the owner's visits or obvious
automated clients.

**Lesson:** request counts are not unique-human counts. Refreshes,
repeated requests, bots, and testing can increase the value.

### Phase 1 --- Browser click-event prototype

A Words2Motion demo click was tagged. JavaScript created an event record
containing information such as event name, project, and timestamp, then
logged it:

``` javascript
console.log("Analytics event:", eventRecord);
```

A project-click event with an ISO timestamp was observed in the console.

**What this proves:** the browser can detect the interaction and
construct an event.\
**What it does not prove:** the event is not yet sent to AWS or stored
persistently. Console logs disappear and cannot support durable
analysis.

### Phase 2 --- Lambda self-traffic and bot filtering

The Lambda was updated to: - Normalize request header names. - Read
query parameters. - Exclude requests carrying `exclude=1`. - Exclude
matching user-agent signatures. - Return the current count with
`excluded: true` for excluded requests. - Increment DynamoDB only for
requests not excluded. - Return JSON with CORS and content-type headers.

The current bot-signature list includes:

``` python
BOT_SIGNATURES = [
    "bot", "crawler", "spider", "slurp",
    "facebookexternalhit", "preview", "headlesschrome",
    "lighthouse", "pingdom", "uptimerobot"
]
```

The exclusion branch reads the current item with DynamoDB `GetItem`; the
normal branch uses `UpdateItem`. The Lambda role needs the relevant
`dynamodb:GetItem` and `dynamodb:UpdateItem` permissions.

**Test --- explicit exclusion:** the endpoint request with `?exclude=1`
returned `{"count": 395, "excluded": true}` and did not increment the
counter at that point.

**Failed browser bot test:** a browser-console `fetch()` attempted to
set `User-Agent: Googlebot`. It returned
`{"count": 413, "excluded": false}` and incremented the counter. This
was not a valid bot test because browsers generally control or forbid
JavaScript from setting the `User-Agent` header.

**Successful Lambda bot test:** a Lambda console test event named
`TestGooglebot` used this simulated event:

``` json
{
  "headers": {
    "user-agent": "Googlebot/2.1 (+http://www.google.com/bot.html)"
  },
  "queryStringParameters": null
}
```

Lambda returned status 200 with body `{"count": 413, "excluded": true}`.
DynamoDB was checked afterward and `visitCount` remained 413.

**Limitations:** user-agent matching is a heuristic, not comprehensive
bot detection. Bots can disguise themselves; legitimate tools can also
match automation-related strings. The `exclude=1` marker is not
authentication and can be spoofed or removed. A browser opt-out cannot
retroactively remove earlier increments.

### Phase 3 --- Browser opt-out

The front-end JavaScript uses a local-storage flag:

``` javascript
const API_URL =
    "https://onhwcq5ckh.execute-api.us-east-1.amazonaws.com/visitor-count";

const EXCLUDE_MY_TRAFFIC_KEY = "portfolio-exclude-my-traffic";

function isExcludedBrowser() {
    return localStorage.getItem(EXCLUDE_MY_TRAFFIC_KEY) === "true";
}
```

When enabled, the counter fetch adds `exclude=1` to the request URL. The
page displays an exclusion message for excluded requests.

Enable in the browser console:

``` javascript
localStorage.setItem("portfolio-exclude-my-traffic", "true");
location.reload();
```

Temporarily disable:

``` javascript
localStorage.setItem("portfolio-exclude-my-traffic", "false");
```

Re-enable:

``` javascript
localStorage.setItem("portfolio-exclude-my-traffic", "true");
```

**Deployment lesson:** local changes do not automatically update the
live site. The change was pushed to GitHub; GitHub Actions and
browser/CloudFront caching were checked. DevTools → Network with
"Disable cache" enabled helped verify the actual deployed JavaScript.
Normal browser caching was restored after troubleshooting.

**Verified:** the live site eventually sent the exclusion parameter when
the local-storage flag was true, showed the exclusion message, and the
backend excluded those requests.

**Not yet verified:** the same opt-out has not been confirmed for
click-event analytics. Add a guard at the start of each analytics event
handler, before logging or sending:

``` javascript
if (isExcludedBrowser()) return;
```

Test that opted-out clicks produce no analytics log or stored event
before connecting events to AWS.

### Phase 4 --- Presistent Analytics Data Collection

  **Objective:** Establish presistent, low-cost storage for portfolio angagement metrics.

  Implementation:
    - Create DynamoDB table ```portfolio-analytics-daily```.
    - Configure ```event_date``` as the partition key and ```metric_key``` as the sort key.
    - Used on-demand capacity.
    - Enabled TTL using ```expires_at```, targeting a 90-day retention period.
    - Stored daily aggregate counts instead of individual event records.
    - Used metric key such as:
        - ```project_click#words2motion```
        - ```section_click#projects```

    Design decisions:
        - Daily aggregation reduces the number of stored records.
        - No raw IP addresses or individual event histories are stored.
        - No secondary indexes were needed for the current reporting requirements.
        - TTL provides automatic expiration, although DynamoDB deletion is asynchronous.

### Phase 5 --- Analytics Collector Lambda

  **Objective:** Validate incoming analytics events and update DynamoDB aggregates.

  Implementation:
    - Created Lambda functin ```portfolio-analytics-collecctor```.
    - Configured environment variable ```ANALYTICS_TABLE```.
    - Created a dedicated IAM role with only the required ```dynamodb:UpdateItem``` permission for the analytics table.
    - Implemented JSON validation and event-type validation.
    - Added allowlists for supported project and section identifiers.
    - Implemented self-traffic exclusion through the ```exclude=1``` query parameter.
    - Added basic bot filtering using user-agent signatures.
    - Used atomic DynamoDB updates with ```if_not_exists``` and increment operations.
    - Added a 90-day expiration timestamp.
  
  Supported project identifiers:
    - ```words2motion```
    - ```github```
    - ```aws-portfolio```

  Supported section identifiers:
    - ```about```
    - ```projects```
    - ```skills```
    - ```contact```

  **Testing:**

  Five local unit test passed:

    1. Valid project event increments the aggregate.
    2. Invalid project indentifier does not write to DynamoDB.
    3. Self-traffic exclusion prevents recording.
    4. Bot filtering prevents recording.
    5. Invalid JSON is rejected.

  The deployed Lambda was also tested successfully with a valid event.

### Phase 6 — API Gateway Integration

  **Objective:** Expose the analytics collector through the existing API Gateway.

  Implementation:
    - Added POST /analytics-event.
    - Connected the route to portfolio-analytics-collector.
    - Enabled automatic deployment.
    - Configured CORS for the production CloudFront portfolio domain.
    - Allowed the content-type header and GET, POST, and OPTIONS methods.
    - Set the CORS max age to 300 seconds.
    
  Testing:
    - Direct API request returned HTTP 200.
    - Valid analytics event was accepted.
    - CORS configuration was tested through the production website.

### Phase 7 — Frontend Analytics Tracking

  **Objective:** Track engagement with portfolio projects and navigation sections.

  Implementation:
    - Added analytics attributes to project links in index.html.
    - Updated js/script.js to identify supported analytics events.
    - Implemented POST requests using fetch() with keepalive: true.
    - Added browser self-exclusion checks.
    - Added navigation-section tracking for About, Projects, Skills, and Contact.
  
  **Testing:**
    - Verified that tracking requests were skipped when self-exclusion was enabled.
    - Verified that valid project events were accepted when exclusion was disabled.
    - Initially encountered stale JavaScript served through CloudFront.
    - Invalidated /js/script.js to ensure production served the updated tracking logic.
    - Confirmed section tracking worked on the production website after invalidation.

  **Known limitation:**

    Every qualifying click is counted, including repeated clicks by the same visitor. These metrics represent click volume, not unique users or sessions.

### Phase 8 — Analytics Dashboard Data Processing

 **Objective:** Retrieve and summarize daily analytics records.

  Implementation:
    - Created Lambda function portfolio-analytics-dashboard.
    - Configured a separate IAM role with dynamodb:Scan and dynamodb:DescribeTable permissions for the analytics table.
    - Implemented paginated DynamoDB scanning.
    - Excluded expired records.
    - Limited reporting to a 90-day window.
    - Aggregated project clicks, section clicks, and daily totals.
    - Returned a JSON summary.

#### Successful test output:

**Metric** | **Test result**
----- | -----
Total clicks | 10
Project clicks | 4
Section clicks | 6

#### Project breakdown:
**Project** | **Clicks**
-----|-----
Words2Motion | 4

#### Section breakdown:
**Section** | **Clicks**
-----|-----
About | 2
Projects | 2
Contact	| 1
Skills	| 1

#### Daily breakdown:
**Date-** | **Project clicks** | **Section clicks** | **Total**
----- | ----- | ----- | -----
Oct. 29	| 4	| 0	 | 4
Oct. 31	| 0	| 6	| 6

**Known limitations:**
    
    - The returned data represents development/testing activity.
    
    - The dashboard Lambda is not yet exposed through an API Gateway route.

    - No Cognito authentication or custom /admin interface has been implemented.

    - A legacy test metric named project_clicked#words2motion exists in DynamoDB. The dashboard currently ignores it because the supported key prefix is project_click#.

## 5. Current Project status
  -----------------------------------------------------------------------
  **Feature** | **Status** | **Notes**
  ------------------------ | ------- | -------
  Portfolio hosting through S3 and CloudFront | Complete
  GitHub Actions frontend deployment | Complete
  Visitor counter | Existing implementation
  Daily analytics DynamoDB table | Complete
  Analytics collector Lambda | Complete 
  API Gateway analytics route | Complete
  Project click tracking | Complete
  Navigation-section tracking | Complete
  Self-traffic exclusion | Implemente | basic filtering
  Bot filtering | Implemented | basic filtering
  Analytics dashboard Lambda | Complete
  Dashboard API endpoint | Not implemented
  S3 analytics export | Planned
  Athena integration | Planned
  Power BI reporting | Planned
  Activity heat map | Planned
  Spatial click heat map | Deferred
  -----------------------------------------------------------------------

  The analytics collection and aggregation pipeline is implemented and has passed functional testing. However, the current test data is not a clean representation of actual portfolio engagement. The next major milestone is establishing the reporting pipeline and creating useful visualization in Power BI.

## 6. Proposed analytics design --- not deployed

### Candidate event fields

  -----------------------------------------------------------------------
  Field                   Example                 Purpose
  ----------------------- ----------------------- -----------------------
  `event_name`            `project_demo_click`    Interaction type

  `target`                `words2motion`          Project, section, or
                                                  button

  `timestamp`             ISO-8601 UTC timestamp  Time-series analysis

  `variant`               `A` or `B`              Experiment comparison

  `session_id`            Random temporary        Approximate session
                          identifier, if needed   analysis

  `page_path`             `/`                     Optional page context

  `referrer_domain`       `github.com`            Optional traffic-source
                                                  analysis
  -----------------------------------------------------------------------

Only include relevant fields per event. Avoid raw IP addresses and
unnecessary identifiers. A session identifier is pseudonymous and does
not prove a real-world identity.

### Geography

Do not assume browser JavaScript can directly read CloudFront
viewer-location headers. Start by reviewing CloudFront's aggregated
geographic reports where available. If per-event country data is later
needed, verify the CloudFront/API configuration, privacy implications,
and incremental cost first.

### Storage and cost decisions to make before creating resources

Compare: 1. Reuse of the existing Lambda/API versus a separate event
endpoint. 2. A dedicated event table versus aggregate-only counters. 3.
Event-level records (more flexible for trends and A/B tests) versus
aggregates (simpler, potentially cheaper). 4. Retention/TTL so records
do not accumulate indefinitely. 5. Request validation, event size
limits, rate controls, and least-privilege IAM. 6. Expected traffic and
incremental API Gateway, Lambda, DynamoDB, logging, and reporting costs.

Do not create AWS resources until event schema, query patterns,
retention, and estimated cost are settled.



### Recommended first persistent-event design (proposed; not deployed)

**Recommendation:** keep the current visitor-counter route and function unchanged. Add a `POST /analytics-event` route to the existing API Gateway HTTP API, backed by a small, separate Lambda function and a dedicated DynamoDB table. This separates counter logic from event ingestion and allows the analytics Lambda role to receive only the permissions it needs. No AWS resources have been created for this design yet.

**Initial event schema:**

| Attribute | Example | Notes |
|---|---|---|
| Partition key `event_date` | `2026-10-28` | UTC date; supports querying a day at a time |
| Sort key `event_key` | `2026-10-28T20:39:00.000Z#<uuid>` | Timestamp plus unique ID; supports chronological queries within a date |
| `event_name` | `project_demo_click` | Must be from a server-side allowlist |
| `target` | `words2motion` | Short allowlisted project/button identifier |
| `variant` | `A` or `B` | Optional until A/B test is implemented |
| `page_path` | `/` | Optional; avoid query strings |
| `referrer_domain` | `github.com` | Optional; store domain only, not full referrer URL |
| `expires_at` | Unix epoch seconds | DynamoDB TTL attribute; proposed 90-day retention |

The server should create the authoritative receive timestamp and event ID, validate payload size and fields, reject unknown event names, and avoid writing events for requests marked as excluded. The browser should send only a small allowlisted event payload. Do not store raw IP addresses, full referrer URLs, names, emails, or a stable user identity. Do not add a session ID until a specific analysis need justifies it.

**Query pattern:** query one `event_date` partition and aggregate events by `event_name`, `target`, and `variant` in the reporting layer. Start without a secondary index; add one only if a real dashboard query cannot be served efficiently by date-based queries. For a small portfolio, this keeps the initial data model simple. TTL deletion is asynchronous, so 90 days is a retention target rather than an exact deletion time.

**Opt-out and bot limits:** keep the existing browser opt-out guard, but also have the analytics Lambda honor the exclusion marker and filter obvious bot user-agent signatures before writing. This is not strong authentication; a public endpoint can be called directly and client-provided signals can be spoofed. Add payload validation and modest rate controls, and never treat the browser opt-out as a security boundary.

**Cost approach:** use the existing HTTP API, a request-driven Lambda, and DynamoDB on-demand billing; do not add provisioned capacity, a continuously running dashboard server, DynamoDB Streams, PITR, or a paid analytics service for the first version. AWS's published examples show HTTP API request pricing by the million and Lambda request charges of $0.20 per million after the applicable free tier; DynamoDB pricing depends on request units, storage, and enabled features. At an illustrative 1,000 small events/month, the direct request/write charges would be tiny (on the order of fractions of a cent before free-tier eligibility), but this is not a complete bill estimate and excludes any extra logging, traffic, taxes, or existing WAF costs. Check the account's actual pricing/free-tier eligibility and billing before deployment. Sources: AWS [API Gateway pricing](https://aws.amazon.com/api-gateway/pricing/), [Lambda pricing](https://aws.amazon.com/lambda/pricing/), and [DynamoDB pricing](https://aws.amazon.com/dynamodb/pricing/).

**Why event-level storage instead of only aggregates?** It supports time trends and future A/B analysis. The trade-off is extra stored data and more careful retention/privacy controls. The 90-day TTL and small allowlisted payload limit that trade-off.

### A/B testing caveats

Assign variants consistently and record the variant with relevant
events. Define the denominator (for example, demo clicks divided by
eligible sessions or page views). Small samples are noisy; do not claim
statistically meaningful improvement without adequate data and an
appropriate analysis.

## 6.1 Final Data Collection Design

  The implemented system uses daily aggregates

  **Attribute** | **Implementation**
  ----- | -----
  Table | ```portfolio-analytics-daily```
  Partition key | ```event_dates```
  Sort key | ```metric_key```
  Project metric | ```project_click#<project>```
  Section metric | ```section_click#<section>```
  Count | Atomic increment
  Retention target | 90 days
  TTL attribute | ```expires_at```
  Capacity mode | On-demand

  The backend determines the event date and expiration timestamp. This prevents the frontend from controlling those values.

## 6.2 Privacy and Traffic filtering

  Current Safeguards:
    - Self-traffic exclusion through the browser's local storage preference and ```exclude=1```.
    - Basic user-agent bot filtering.
    - Project and section allowlists.
    - No raw IP storage
    - No individual event-leevel records.
    - Daily aggregate storage.

  Limitation:
    - These safeguards reduce unwanted traffic but do not provide guaranteed indentification of bots or all development traffic. The resulting metrics should be interpreted as filtered click activity rather than verified human engagement.

## 6.3 Reporting Platform Decision

  Microsoft Power BI was selected as the primary reporting platform to provide practical experience with business intelligence tools and data visualization. Rathen than immediately creating a custom authenticated dashboard inside the portfolio, the reporting architecture will use DynamoDB daily aggregates, S3 exports, and Athena queries to make data accessible to Power BI.
  This approach separates data collection from reporting and provides an opportunity to practice SQL-based analytics, data modeling, and dashboard development.


## 7. Interview study notes

### What each AWS service does

-   **S3:** stores static website assets such as HTML, CSS, JavaScript,
    and images.
-   **CloudFront:** CDN that caches and serves assets from edge
    locations; can integrate with AWS WAF.
-   **GitHub Actions:** automates deployment when code is pushed to the
    configured branch.
-   **API Gateway HTTP API:** provides an HTTPS endpoint and routes
    requests to Lambda.
-   **Lambda:** runs serverless Python code in response to requests.
-   **DynamoDB:** managed NoSQL database storing the counter and
    potentially future event records.
-   **AWS WAF:** filters web requests using configured rules; it is an
    additional layer, not a guarantee that all malicious requests are
    blocked.

### Why use DynamoDB `UpdateItem` with `ADD`?

The atomic numeric `ADD` operation increments the counter without the
application reading the old value and writing a replacement. This avoids
a common race condition where concurrent requests could overwrite each
other's increments.

### Why filter before incrementing?

The backend must decide whether to exclude a request before performing
the write. A front-end-only filter is easy to bypass and cannot stop
direct calls to a public endpoint. The current design uses a query
marker and user-agent heuristic; both have limitations.

### CORS versus security

CORS controls whether browser JavaScript from another origin can read a
cross-origin response. It is not authentication and does not prevent
non-browser clients from calling a public API. The current Lambda
response includes `Access-Control-Allow-Origin: *`; changes should be
deliberate and tested with the deployed site.

### What does "unique visitor" mean?

A request count is not a unique-visitor count. Browser storage can
estimate distinct browsers or sessions, but users can clear storage, use
multiple devices, or share a device. Bots can evade simple filters. Use
precise labels such as "filtered counter requests" or "estimated browser
sessions," not "unique people."

### Deployment and caching

A local edit must be committed, pushed, and successfully deployed before
it reaches the live site. Browser and CloudFront caches can serve older
assets. Verify the workflow and actual Network response before assuming
deployment succeeded.

### Why store daily aggregates instead of individual events?

Daily aggregation reduces the number of records stored and avoids retaining individual click histories. It also makes the current reporting requirements simpler to query.

### Why separate the collector and dashboard Lambdas?

The collector is responsible for validating and writing incoming events. The dashboard Lambda is responsible for reading stored records and producing summaries. Separating these responsibilities makes the premission and maintenance easier to manage.


## 8. Next steps

### Immediate
-   [ ] Review the DynamoDB rest records and identify development-only data that should be excluded from the first reporting baseline.
-   [ ] Confirm the dashboard Lambda's output and aggregation logic are correct.
-   [ ] Design and implement a scheduled or controlled S3 export of the daily aggregates.
-   [ ] Create an Athena external table over the exported data.
-   [ ] Validate the Athena results against DynamoDB dashboard output.

### Power BI reporting
-   [ ] Configure the Power BI connection to Athena.
-   [ ] Build the initial data model.
-   [ ] Create a date-by-category activity heat map.
-   [ ] Add project and section engagement summaries.
-   [ ] Add daily and monthly activity trends.

###Later Improvements
-   [ ] Establish a clean engagement baseline.
-   [ ] Compare portfolio engagement before and after UX changes.
-   [ ] Explore A/B testing.
-   [ ] Consider spatial click heat maps using normalized click coordinates and viewport information, following separate privacy review.

## 9. Change-log template

Append an entry after each meaningful implementation or test, including
failures.

``` markdown
### YYYY-MM-DD — Short change title

**Goal:** What problem were we solving?

**Concepts learned:** What technical concept does this illustrate?

**Implementation:** What changed? Name files, functions, and resources.

**Test:** What exact test was performed?

**Observed result:** What happened? Include relevant output or measurements.

**Conclusion:** What does the result prove, and what does it not prove?

**Cost/security/privacy impact:** New charges, permissions, data collected, or risks.

**Next step:** The next small action.
```

### 2026-10-28 --- Click-event opt-out verification

**Goal:** Ensure the owner can exclude their own project-click events from the browser-side analytics prototype.

**Implementation:** The existing `projectLinks` click handler checks `isExcludedBrowser()` before creating or logging `eventRecord`. When the flag is true, the handler returns early.

**Tests and observed results:** With `portfolio-exclude-my-traffic` set to `true`, clicking the Words2Motion demo produced no analytics event log. With the flag set to `false`, the expected event log appeared. The flag was restored to `true` after testing.

**Conclusion:** The browser-side self-traffic guard passed both tests. This verifies console logging behavior only; click events are not yet sent to or stored in AWS.

**Cost/security/privacy impact:** No AWS resources or charges were added. The local-storage preference is browser-specific and can be cleared by the user.

**Next step:** Finalize a minimal persistent event schema, query patterns, retention, request validation, and incremental cost assumptions before provisioning.

### 2026-10-28 --- Baseline, self-traffic exclusion, and bot-filter checkpoint

**Goal:** Make the existing visitor counter more honest before adding
persistent analytics.

**Implementation:** Added a Lambda exclusion path using `exclude=1`, a
user-agent signature filter, and a browser local-storage opt-out named
`portfolio-exclude-my-traffic`. The visitor-count request adds the
exclusion query parameter when the preference is enabled.

**Observed tests:** - `?exclude=1` returned `excluded: true` and did not
increment the count. - Browser attempts to spoof `User-Agent` were not a
valid bot-filter test and did increment the count. - A simulated
Googlebot event in Lambda returned `excluded: true`. - DynamoDB was
checked after the simulated bot test; `visitCount` remained 413. - Live
browser exclusion was verified after deployment and cache
troubleshooting.

**Conclusion:** Explicit self-traffic exclusion and a basic Googlebot
signature work in the tested paths. They do not establish comprehensive
bot detection. The existing count is mixed historical traffic and must
not be relabeled as filtered.

**Cost/security/privacy impact:** No new AWS resources were created for
this phase. WAF remains enabled. The public endpoint's exclusion query
parameter is not authentication.

**Next step:** Verify the self-traffic guard for click analytics, then
finalize event schema, retention, and cost estimates before provisioning
persistent event storage.

### 2026-10-29 — Implemented Persistent Daily Analytics Storage

**Goal:** Establish persistent storage for portfolio engagement metrics without retaining individual click events.

**Concepts learned:** DynamoDB partition keys and sort keys, on-demand capacity, TTL expiration, and daily aggregation.

**Implementation:**
- Created DynamoDB table `portfolio-analytics-daily`.
- Configured `event_date` as the partition key and `metric_key` as the sort key.
- Enabled on-demand capacity.
- Configured `expires_at` as the TTL attribute, targeting 90-day retention.
- Established metric-key formats such as `project_click#words2motion` and `section_click#projects`.

**Test:** Verified that the table was created with the expected key schema, capacity mode, and TTL configuration.

**Observed result:** The table was available for storing daily aggregate records. TTL was configured, but expiration is asynchronous and does not guarantee deletion exactly 90 days after an event.

**Conclusion:** The persistent storage foundation was established for daily analytics aggregation. This does not establish that the collected metrics represent genuine visitor engagement.

**Cost/security/privacy impact:** On-demand capacity avoids provisioning fixed read/write capacity. No raw IP addresses or individual event histories are stored. TTL targets automatic cleanup after 90 days.

**Next step:** Implement a Lambda function that validates incoming events and updates the daily aggregates.

### 2026-10-29 — Implemented Analytics Collector Lambda

**Goal:** Process incoming portfolio analytics events and update the corresponding DynamoDB aggregate safely.

**Concepts learned:** Lambda execution roles, least-privilege IAM, input validation, atomic DynamoDB updates, and event filtering.

**Implementation:**
- Created Lambda function `portfolio-analytics-collector`.
- Configured environment variable `ANALYTICS_TABLE=portfolio-analytics-daily`.
- Created a dedicated execution role with `dynamodb:UpdateItem` permission scoped to the analytics table.
- Implemented JSON validation, event-type validation, and project/section allowlists.
- Added self-traffic exclusion through the `exclude=1` query parameter.
- Added basic bot filtering using user-agent signatures.
- Used atomic DynamoDB updates with `if_not_exists` and increment operations.
- Added a 90-day expiration timestamp.
- Created local files `analytics-lambda/lambda_function.py` and `analytics-lambda/test_lambda_function.py`.

**Test:** Ran `python -m unittest -v` against five test cases covering valid project increments, invalid project identifiers, self-traffic exclusion, bot exclusion, and invalid JSON. Also tested the deployed Lambda with a valid analytics event.

**Observed result:** All five local unit tests passed. The initial AWS test encountered a `NameError` because `BOT_SIGNATURES` was not defined; after correcting the issue, the deployed Lambda successfully processed a valid event and wrote the expected `project_click#words2motion` metric.

**Conclusion:** The collector can validate supported events, reject invalid or excluded requests, and update daily aggregates. These tests do not prove that all bots or development traffic will be identified.

**Cost/security/privacy impact:** The Lambda uses a dedicated role with only the required DynamoDB update permission. No raw IP addresses or individual event records are stored. Lambda invocations and DynamoDB writes introduce usage-based charges.

**Next step:** Connect the collector Lambda to an API Gateway route so the portfolio frontend can submit analytics events.

### 2026-10-29 — Integrated Analytics Collector with API Gateway

**Goal:** Provide an HTTP endpoint for the portfolio frontend to submit analytics events.

**Concepts learned:** API Gateway HTTP API routes, Lambda integrations, CORS, and HTTP request handling.

**Implementation:**
- Added `POST /analytics-event` to the existing HTTP API.
- Integrated the route with `portfolio-analytics-collector`.
- Enabled automatic deployment.
- Configured CORS for the production CloudFront domain.
- Allowed the `content-type` header and GET, POST, and OPTIONS methods.
- Configured a CORS max age of 300 seconds.

**Test:** Sent a direct POST request containing a valid analytics event to the new endpoint.

**Observed result:** The endpoint returned HTTP 200 and accepted the valid event.

**Conclusion:** API Gateway successfully routes analytics requests to the collector Lambda. This test does not establish that frontend tracking is working or that all production requests will be valid.

**Cost/security/privacy impact:** API Gateway requests and Lambda invocations introduce usage-based charges. CORS restricts browser access to the configured origin, but it is not authentication and does not prevent arbitrary clients from calling the endpoint.

**Next step:** Implement frontend event tracking for portfolio project links.

### 2026-10-30 — Implemented Frontend Project Click Tracking

**Goal:** Track how often visitors interact with portfolio project links.

**Concepts learned:** HTML data attributes, JavaScript event listeners, asynchronous HTTP requests, and browser request lifecycle behavior.

**Implementation:**
- Added `data-analytics-event="project_click"` attributes to supported project links in `index.html`.
- Added project identifiers for `words2motion`, `github`, and `aws-portfolio`.
- Updated `js/script.js` to identify tracked project links.
- Implemented POST requests to the analytics endpoint using `fetch()` with `keepalive: true`.
- Added browser self-exclusion checks using the existing `isExcludedBrowser()` functionality.

**Test:** Tested project-link tracking in the browser with self-exclusion enabled and disabled.

**Observed result:** With self-exclusion enabled, the browser did not submit an analytics request. With exclusion disabled, the request reached the API and returned HTTP 200 with `accepted: true`.

**Conclusion:** The frontend can submit supported project-click events to the backend, and the self-exclusion setting prevents the tested browser from submitting them. The metric counts clicks, including repeated clicks by the same visitor; it does not represent unique visitors or sessions.

**Cost/security/privacy impact:** Each qualifying click can generate an API Gateway request, Lambda invocation, and DynamoDB update. No raw IP address or individual event history is collected.

**Next step:** Extend the tracking implementation to portfolio navigation sections.

### 2026-10-30 — Implemented Navigation Section Tracking

**Goal:** Measure engagement with the portfolio's About, Projects, Skills, and Contact navigation links.

**Concepts learned:** Reusing frontend event-tracking logic, HTML data attributes, and CloudFront cache invalidation.

**Implementation:**
- Added analytics attributes to the About, Projects, Skills, and Contact navigation links.
- Updated `js/script.js` with navigation-section tracking logic.
- Used the existing analytics endpoint and collector rather than creating a separate backend route.
- Invalidated `/js/script.js` on the production CloudFront distribution after discovering that the live site was serving an older cached script.

**Test:** Verified section tracking locally, inspected the production JavaScript response, and tested a navigation-section event against the live analytics endpoint after invalidation.

**Observed result:** Production initially failed to submit section events because CloudFront was serving stale JavaScript. After invalidating `/js/script.js`, the live script contained the section-tracking logic and production section tracking returned HTTP 200.

**Conclusion:** Project and navigation-section tracking now share the same backend collection pipeline. The production test confirms that the updated frontend code can submit section events; it does not establish clean or representative engagement metrics.

**Cost/security/privacy impact:** CloudFront invalidation may incur charges depending on usage and applicable allowances. Section clicks generate additional API requests and DynamoDB updates. No additional personal information is collected.

**Next step:** Create a backend process that retrieves and summarizes stored analytics records.

### 2026-10-31 — Implemented Analytics Dashboard Lambda

**Goal:** Retrieve daily aggregate records and produce a summarized analytics response for reporting.

**Concepts learned:** DynamoDB Scan operations, pagination, Lambda IAM permissions, data aggregation, and JSON response formatting.

**Implementation:**
- Created Lambda function `portfolio-analytics-dashboard`.
- Configured environment variable `ANALYTICS_TABLE=portfolio-analytics-daily`.
- Created a separate execution role with `dynamodb:Scan` and `dynamodb:DescribeTable` permissions scoped to the analytics table.
- Implemented paginated DynamoDB scanning.
- Excluded expired records and limited reporting to a 90-day window.
- Aggregated project clicks, section clicks, and daily totals.
- Corrected an initial aggregation issue that caused project clicks to be included in daily section-click totals.
- Corrected a logger method typo encountered during testing.

**Test:** Invoked the deployed dashboard Lambda and inspected its JSON response.

**Observed result:** A successful test returned:
- Total clicks: 10
- Project clicks: 4
- Section clicks: 6
- Words2Motion clicks: 4
- About: 2
- Projects: 2
- Contact: 1
- Skills: 1

The daily breakdown reported four project clicks on October 29 and six section clicks on October 31.

A legacy test metric, `project_clicked#words2motion`, also exists in DynamoDB. The dashboard ignores it because the supported project metric prefix is `project_click#`.

**Conclusion:** The dashboard Lambda can retrieve and aggregate the supported daily analytics records into a JSON summary. The output reflects development/testing activity, not a clean measure of actual visitor engagement. The Lambda is not yet exposed through an API Gateway route.

**Cost/security/privacy impact:** The dashboard uses a separate role with read-oriented permissions for the analytics table. DynamoDB scanning can consume read capacity and should be monitored as the dataset grows. No individual event histories are retrieved because the table stores aggregates.

**Next step:** Establish a reporting pipeline that makes the aggregated data accessible to Microsoft Power BI.

### 2026-11-06 — Selected Microsoft Power BI for Analytics Reporting

**Goal:** Choose a reporting platform for analyzing portfolio engagement and visualizing the collected metrics.

**Concepts learned:** Business intelligence reporting, data pipelines, SQL-based analytics, data modeling, and dashboard visualization.

**Implementation:** Selected Microsoft Power BI as the primary reporting and visualization platform. Established the proposed architecture:

DynamoDB daily aggregates → S3 export → Amazon Athena → Microsoft Power BI.

Identified a date-by-category activity heat map as the first planned visualization. Spatial click heat maps were deferred to a later phase.

**Test:** Compared the proposed reporting direction against the existing DynamoDB schema and dashboard Lambda output. No S3 export, Athena integration, or Power BI connection was implemented or tested as part of this decision.

**Observed result:** The existing daily aggregate structure provides a foundation for reporting by date, project, and portfolio section. The proposed reporting pipeline remains unimplemented.

**Conclusion:** Power BI is the selected reporting platform, and the proposed architecture provides a path from stored analytics data to interactive reporting. This decision does not prove that the Athena connector, export process, or Power BI dashboard is operational.

**Cost/security/privacy impact:** S3 storage, Athena queries, and Power BI licensing or connectivity may introduce additional costs. The existing aggregate-based privacy approach will be retained. Access to exported data and reporting resources will need to be configured appropriately.

**Next step:** Investigate and implement a controlled export of the daily DynamoDB aggregates to S3.

## 10. Keeping this report current

-   Update after each milestone, not just at the end.
-   Clearly separate implemented, tested, and planned work.
-   Record observed outputs and cost periods; omit credentials, account
    IDs, internal resource IDs, sampled IPs, and secrets.
-   Keep interview explanations and debugging lessons alongside the
    implementation log.
-   Review the report for private identifiers before publishing it
    publicly.


### 2026-10-28 --- Persistent analytics design checkpoint

**Goal:** Choose a low-cost architecture for storing click events without risking the existing visitor counter.

**Decision proposed:** Add `POST /analytics-event` to the existing API Gateway HTTP API, route it to a separate Lambda function, and store validated event records in a dedicated DynamoDB table. Keep the current visitor-counter route/function unchanged.

**Schema/query design:** Partition by UTC `event_date`; sort by timestamp plus UUID. Store an allowlisted event name and target, optional A/B variant, optional path/referrer domain, and a TTL epoch timestamp. Start with date-based queries and no secondary index. Target 90-day retention; DynamoDB TTL deletion is asynchronous.

**Privacy/security:** Do not store raw IP addresses, full referrer URLs, or direct identity data. Validate event names, fields, and payload size server-side. Keep the browser opt-out and honor exclusion signals server-side, while recognizing that public query flags and user-agent heuristics can be spoofed. Use a least-privilege role for the analytics Lambda.

**Cost approach:** Reuse the current API Gateway API; use request-driven Lambda and DynamoDB on-demand capacity; avoid always-on compute and optional features until justified. A 1,000-event/month example implies very small direct request/write charges, but actual costs depend on account free-tier eligibility, data volume, logging, and existing services. Official pricing references were checked for API Gateway, Lambda, and DynamoDB.

**Implementation status:** Design only. No AWS resources were created and no event has yet been stored persistently.

**Next step:** Confirm the approximate event volume and review the design/cost assumptions, then implement one small endpoint and test valid, excluded, malformed, and existing-counter requests before building the dashboard.

### 2026-11-06 -- Persistent Analytics Implementation and Reporting Direction

**Goal:**

Establish persistent, privacy-conscious portfolio engagement tracking and determine a reporting approach for analyzing project and navigation-section interactions.

**Decision Proposed:**

Use daily aggregate records in DynamoDB as the persistent analytics storage layer. Use Microsoft Power BI as the primary reporting and visualization platform, with the proposed data pipeline:

DynamoDB → S3 → Amazon Athena → Microsoft Power BI.

The first planned visualization is a date-by-category activity heat map showing engagement across portfolio projects and navigation sections. Spatial click heat maps are deferred until a later phase.

**Schema/query design:**

DynamoDB table: `portfolio-analytics-daily`

- Partition key: `event_date` (String)
- Sort key: `metric_key` (String)
- Project metric format: `project_click#<project>`
- Section metric format: `section_click#<section>`
- Count: Atomically incremented aggregate value
- TTL attribute: `expires_at`
- Retention target: 90 days

The collector Lambda validates event types and supported identifiers before updating the daily aggregate. The dashboard Lambda scans the table with pagination, excludes expired records, and summarizes project clicks, section clicks, and daily totals over a 90-day reporting window.

The future S3/Athena reporting layer should preserve the date, metric category, identifier, and count fields needed to query engagement by date and category.

**Privacy/security:**

- Store daily aggregate counts rather than individual click records.
- Do not store raw IP addresses.
- Validate event types and use project/section allowlists.
- Support self-traffic exclusion through the browser preference and `exclude=1` parameter.
- Apply basic bot filtering using user-agent signatures.
- Use separate Lambda execution roles with permissions scoped to the analytics table.
- Treat CORS as a browser-origin control, not an authentication mechanism.
- Review access permissions for future S3 exports, Athena queries, and Power BI reporting.

The current filtering is not guaranteed to identify every bot or exclude all development traffic.

**Cost approach:**

- Use DynamoDB on-demand capacity.
- Retain a 90-day expiration target through TTL.
- Store aggregate records to limit storage growth.
- Monitor DynamoDB scans and Lambda/API Gateway usage.
- Evaluate S3 storage, Athena query costs, and Power BI licensing/connectivity costs before implementing the reporting pipeline.

**Implementation status:**

Implemented and functionally tested:
- DynamoDB daily aggregate table.
- Analytics collector Lambda.
- API Gateway `POST /analytics-event` route.
- Frontend project-click tracking.
- Frontend navigation-section tracking.
- Browser self-traffic exclusion and basic bot filtering.
- Dashboard Lambda with 90-day aggregation and JSON output.

Not yet implemented:
- S3 analytics export.
- Athena external table and SQL queries.
- Power BI connection and dashboard.
- Date-by-category activity heat map.
- Spatial click heat map.

The dashboard Lambda is not currently exposed through an API Gateway route. The existing test output contains development/testing activity and is not a clean visitor-engagement baseline.

**Next step:**

Implement and validate a controlled export of the daily DynamoDB aggregate records to S3, then create an Athena table and verify its query results against the existing dashboard Lambda output.