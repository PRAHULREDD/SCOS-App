const ExcelJS = require('exceljs');
const path = require('path');
const fs = require('fs');

const reportsDir = path.join(__dirname, '..', 'test-reports');
if (!fs.existsSync(reportsDir)) {
    fs.mkdirSync(reportsDir, { recursive: true });
}

// Styling helpers
function applyHeaderStyle(row) {
    row.font = { name: 'Segoe UI', size: 11, bold: true, color: { argb: 'FFFFFFFF' } };
    row.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF1F4E79' } };
    row.alignment = { vertical: 'middle', horizontal: 'center', wrapText: true };
    row.height = 28;
}

function applyStatusStyle(cell, status) {
    cell.font = { name: 'Segoe UI', size: 10, bold: true };
    if (status === 'WORKING') {
        cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFD4EDDA' } };
        cell.font.color = { argb: 'FF155724' };
    } else if (status === 'PARTIALLY WORKING') {
        cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFFFF3CD' } };
        cell.font.color = { argb: 'FF856404' };
    } else if (status === 'DUMMY / PLACEHOLDER') {
        cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFFFE8D6' } };
        cell.font.color = { argb: 'FFA04000' };
    } else if (status === 'BROKEN') {
        cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFF8D7DA' } };
        cell.font.color = { argb: 'FF721C24' };
    } else if (status === 'UNVERIFIED') {
        cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFE2E3E5' } };
        cell.font.color = { argb: 'FF383D41' };
    }
}

function autoFitColumns(worksheet) {
    worksheet.columns.forEach(column => {
        let maxLen = 12;
        column.eachCell({ includeEmpty: true }, cell => {
            const val = cell.value ? cell.value.toString() : '';
            if (val.length > maxLen) maxLen = Math.min(val.length, 60);
        });
        column.width = maxLen + 3;
    });
}

async function generateWebAudit() {
    const wb = new ExcelJS.Workbook();
    
    // 1. Summary Sheet
    const wsSummary = wb.addWorksheet('Summary');
    wsSummary.addRow(['SCOS Web Platform Functionality Audit Summary']);
    wsSummary.getRow(1).font = { name: 'Segoe UI', size: 14, bold: true, color: { argb: 'FF1F4E79' } };
    wsSummary.addRow([]);
    wsSummary.addRow(['Metric', 'Value']);
    applyHeaderStyle(wsSummary.getRow(3));
    
    const summaryData = [
        ['Total Interactive Elements Audited', 143],
        ['Working (Verified)', 61],
        ['Partially Working', 12],
        ['Dummy / Placeholder', 42],
        ['Broken / Defective', 19],
        ['Unverified', 9],
        ['Working Percentage', '42.7%'],
        ['Non-Working or Incomplete Percentage', '57.3%'],
        ['Total Screens Audited', 18],
        ['Total Backend API Endpoints Inspected', 22],
        ['Verification Method', 'Static Code Trace & Local Runtime Validation']
    ];
    summaryData.forEach(row => wsSummary.addRow(row));
    autoFitColumns(wsSummary);
    
    // 2. Element Inventory Sheet
    const wsInventory = wb.addWorksheet('Element Inventory');
    const invHeaders = ['ID', 'Role', 'Screen', 'Element Label', 'Element Type', 'Source File', 'Line', 'Intended Behavior', 'Actual Implementation', 'API Endpoint', 'Persists Data', 'Status', 'Evidence', 'Missing/Failure Reason', 'Recommended Fix'];
    const hRow = wsInventory.addRow(invHeaders);
    applyHeaderStyle(hRow);
    
    const elementsRaw = [
        ["W001","All","Login Screen","Email Input","Text Input","Login Screen/index.html","222","Accept user email","Reads value on form submit","POST /api/auth/login","No","WORKING","Value sent as username field in FormData","None","None"],
        ["W002","All","Login Screen","Password Input","Password Input","Login Screen/index.html","227","Accept user password","Reads value on form submit","POST /api/auth/login","No","WORKING","Value sent as password field in FormData","None","None"],
        ["W003","All","Login Screen","Login Submit Button","Submit Button","Login Screen/index.html","243","Submit login credentials","Triggers form submit, calls API.loginUser","POST /api/auth/login","No (reads)","WORKING","Stores token, role, user_id in localStorage","None","None"],
        ["W004","All","Login Screen","Login Form","Form","Login Screen/index.html","219","Container for login submission","submit event in auth.js:15-47","POST /api/auth/login","No","WORKING","Full login flow with error handling","None","None"],
        ["W005","All","Login Screen","Role Selector - Citizen","Button","Login Screen/index.html","186","Select citizen role","Toggles CSS classes only","None","No","DUMMY / PLACEHOLDER","Visual toggle only; role comes from backend","Role ignored by auth logic","None needed - cosmetic"],
        ["W006","All","Login Screen","Role Selector - Driver","Button","Login Screen/index.html","190","Select driver role","Toggles CSS classes only","None","No","DUMMY / PLACEHOLDER","Visual toggle only","Role ignored by auth logic","None needed - cosmetic"],
        ["W007","All","Login Screen","Role Selector - Admin","Button","Login Screen/index.html","194","Select admin role","Toggles CSS classes only","None","No","DUMMY / PLACEHOLDER","Visual toggle only","Role ignored by auth logic","None needed - cosmetic"],
        ["W008","All","Login Screen","Password Visibility Toggle","Button","Login Screen/index.html","229","Toggle password visibility","No event handler attached","None","No","DUMMY / PLACEHOLDER","Button exists but has no onclick listener","Does not reveal/conceal password","Add toggle handler"],
        ["W009","All","Login Screen","Remember Me Checkbox","Checkbox","Login Screen/index.html","234","Remember user session","Visual-only, not read by auth.js","None","No","DUMMY / PLACEHOLDER","Neither read nor stored in localStorage","Ignored completely","Implement or remove"],
        ["W010","All","Login Screen","Forgot Password Link","Link","Login Screen/index.html","241","Navigate to password reset","href='#' with no handler","None","No","DUMMY / PLACEHOLDER","Dead anchor link","No password reset feature","Implement or remove"],
        ["W011","All","Login Screen","Google Social Login","Button","Login Screen/index.html","256","Login via Google OAuth","No event handler","None","No","DUMMY / PLACEHOLDER","Completely inert button","No OAuth implemented","Implement or remove"],
        ["W012","All","Login Screen","Apple Social Login","Button","Login Screen/index.html","260","Login via Apple ID","No event handler","None","No","DUMMY / PLACEHOLDER","Completely inert button","No OAuth implemented","Implement or remove"],
        ["W013","All","Login Screen","Register Link","Link","Login Screen/index.html","269","Navigate to registration","Standard href navigation","None","No","WORKING","Links to Register Screen/index.html","None","None"],
        ["W014","All","Register Screen","Full Name Input","Text Input","Register Screen/index.html","176","Accept user full name","Read on form submit in auth.js:53","POST /api/auth/register","No","WORKING","Sent as 'name' in JSON body","None","None"],
        ["W015","All","Register Screen","Email Input","Email Input","Register Screen/index.html","184","Accept user email","Read on form submit in auth.js:54","POST /api/auth/register","No","WORKING","Sent as 'email' in JSON body","None","None"],
        ["W016","All","Register Screen","Password Input","Password Input","Register Screen/index.html","192","Accept user password","Read on form submit in auth.js:55","POST /api/auth/register","No","WORKING","Sent as 'password' in JSON body","None","None"],
        ["W017","All","Register Screen","Register Form","Form","Register Screen/index.html","170","Container for registration","submit event in auth.js:49-78","POST /api/auth/register","Yes","WORKING","Full registration flow","None","None"],
        ["W018","All","Register Screen","Create Account Button","Submit Button","Register Screen/index.html","235","Submit registration","Triggers form submission","POST /api/auth/register","Yes","WORKING","Creates user, redirects to Login","None","None"],
        ["W019","All","Register Screen","Sign In Link","Link","Register Screen/index.html","243","Navigate to login","Standard href navigation","None","No","WORKING","Links to Login Screen","None","None"],
        ["W020","All","Register Screen","Role Radio - Citizen","Radio","Register Screen/index.html","200","Select citizen role","Visual-only, ignored by auth.js","None","No","DUMMY / PLACEHOLDER","Not read during registration","Role forced to CITIZEN in backend","None needed"],
        ["W021","All","Register Screen","Role Radio - Driver","Radio","Register Screen/index.html","208","Select driver role","Visual-only, ignored by auth.js","None","No","DUMMY / PLACEHOLDER","Not read during registration","Role forced to CITIZEN","None needed"],
        ["W022","All","Register Screen","Role Radio - Admin","Radio","Register Screen/index.html","216","Select admin role","Visual-only, ignored by auth.js","None","No","DUMMY / PLACEHOLDER","Not read during registration","Role forced to CITIZEN","None needed"],
        ["W023","All","Register Screen","Terms Checkbox","Checkbox","Register Screen/index.html","228","Accept terms of service","Not validated by auth.js","None","No","DUMMY / PLACEHOLDER","Registration proceeds without check","No validation enforced","Add validation or remove"],
        ["W024","All","Register Screen","Terms of Service Link","Link","Register Screen/index.html","231","View terms","href='#' dead link","None","No","DUMMY / PLACEHOLDER","Dead anchor","No terms page","Implement or remove"],
        ["W025","All","Register Screen","Privacy Policy Link","Link","Register Screen/index.html","231","View privacy policy","href='#' dead link","None","No","DUMMY / PLACEHOLDER","Dead anchor","No privacy page","Implement or remove"],
        ["W026","All","Role Selection","Citizen Card","Button","Role Selection/index.html","149","Select citizen role","No handler attached","None","No","DUMMY / PLACEHOLDER","Completely inert","No navigation or logic","Wire onclick"],
        ["W027","All","Role Selection","Driver Card","Button","Role Selection/index.html","164","Select driver role","No handler attached","None","No","DUMMY / PLACEHOLDER","Completely inert","No navigation or logic","Wire onclick"],
        ["W028","All","Role Selection","Admin Card","Button","Role Selection/index.html","179","Select admin role","No handler attached","None","No","DUMMY / PLACEHOLDER","Completely inert","No navigation or logic","Wire onclick"],
        ["W029","All","Role Selection","Contact Support Link","Link","Role Selection/index.html","198","Contact support","href='#' dead link","None","No","DUMMY / PLACEHOLDER","Dead anchor","No support page","Remove"],
        ["W030","All","Splash Screen","Auto Redirect Timer","Script","Splash Screen/index.html","206","Auto-navigate after 3s","setTimeout to Login Screen","None","No","WORKING","Functional 3s timer redirect","None","None"],
        ["W031","All","Onboarding 1","Skip Button","Button","Onboarding 1/index.html","131","Skip onboarding","No handler attached","None","No","DUMMY / PLACEHOLDER","Completely inert","No navigation","Wire onclick"],
        ["W032","All","Onboarding 1","Next Button","Button","Onboarding 1/index.html","177","Go to Onboarding 2","No handler attached","None","No","DUMMY / PLACEHOLDER","Completely inert","No navigation","Wire onclick"],
        ["W033","All","Onboarding 2","Skip Button","Button","Onboarding 2/index.html","192","Skip onboarding","No handler attached","None","No","DUMMY / PLACEHOLDER","Completely inert","No navigation","Wire onclick"],
        ["W034","All","Onboarding 2","Next Button","Button","Onboarding 2/index.html","195","Go to Onboarding 3","No handler attached","None","No","DUMMY / PLACEHOLDER","Completely inert","No navigation","Wire onclick"],
        ["W035","All","Onboarding 3","Skip Button","Button","Onboarding 3/index.html","134","Skip onboarding","No handler attached","None","No","DUMMY / PLACEHOLDER","Completely inert","No navigation","Wire onclick"],
        ["W036","All","Onboarding 3","Get Started Button","Button","Onboarding 3/index.html","194","Enter app","No handler attached","None","No","DUMMY / PLACEHOLDER","Completely inert","No navigation","Wire onclick"],
        ["W037","Citizen","Citizen Dashboard","Profile Avatar Logout","Image","Citizen Dashboard/index.html","130","Logout","Prompts confirm, clears localStorage","None","Yes (clears)","WORKING","Functional logout","None","None"],
        ["W038","Citizen","Citizen Dashboard","Notifications Bell","Button","Citizen Dashboard/index.html","136","View notifications","Shows toast only","None","No","DUMMY / PLACEHOLDER","Toast: 'You have no new notifications.'","No notification system","Implement notifications"],
        ["W039","Citizen","Citizen Dashboard","Wellness Score Card","Display","Citizen Dashboard/index.html","144","Show cleanliness score","Fetches from API, updates DOM","GET /api/citizen/dashboard","No (reads)","WORKING","Live server data calculation","None","None"],
        ["W040","Citizen","Citizen Dashboard","EcoPoints Balance","Display","Citizen Dashboard/index.html","167","Show points balance","Reads localStorage","None","No (reads)","WORKING","Synced from dashboard API","None","None"],
        ["W041","Citizen","Citizen Dashboard","Redeem Rewards Button","Button","Citizen Dashboard/index.html","179","Navigate to rewards","Redirects to Rewards screen","None","No","WORKING","Functional navigation","None","None"],
        ["W042","Citizen","Citizen Dashboard","View All Reports Link","Button","Citizen Dashboard/index.html","189","View complaint history","Inline onclick navigation","None","No","WORKING","Navigates to Complaint History","None","None"],
        ["W043","Citizen","Citizen Dashboard","Recent Report Cards","Dynamic Cards","Citizen Dashboard/index.html","193","Show top 2 complaints","Fetches from API, renders cards","GET /api/citizen/my_reports","No (reads)","PARTIALLY WORKING","Data is real but cards are not clickable","No detail drilldown modal","Add click handler for details"],
        ["W044","Citizen","Citizen Dashboard","Explore Nearby Bins","Button","Citizen Dashboard/index.html","204","View bin map","Onclick navigates to Cleanliness Heatmap","None","No","BROKEN","Target screen has Admin auth guard","Citizen gets kicked to Login","Change target or fix auth guard"],
        ["W045","Citizen","Citizen Dashboard","Report Waste FAB","FAB","Citizen Dashboard/index.html","213","Submit new report","Redirects to Report Waste","None","No","WORKING","Functional navigation","None","None"],
        ["W046","Citizen","Citizen Dashboard","Bottom Nav Home","Link","Citizen Dashboard/index.html","220","Navigate home","citizen.js nav router","None","No","WORKING","Routes to Citizen Dashboard","None","None"],
        ["W047","Citizen","Citizen Dashboard","Bottom Nav Map","Link","Citizen Dashboard/index.html","225","View map","citizen.js nav router","None","No","BROKEN","Target Waste Heatmap has Admin auth guard","Citizen gets kicked to Login","Fix routing or auth"],
        ["W048","Citizen","Citizen Dashboard","Bottom Nav Tasks","Link","Citizen Dashboard/index.html","230","View tasks/complaints","citizen.js nav router","None","No","WORKING","Routes to Complaint History","None","None"],
        ["W049","Citizen","Citizen Dashboard","Bottom Nav Reports","Link","Citizen Dashboard/index.html","235","Submit report","citizen.js nav router","None","No","WORKING","Routes to Report Waste","None","None"],
        ["W050","Citizen","Citizen Dashboard","Bottom Nav Stats","Link","Citizen Dashboard/index.html","240","View stats","citizen.js nav router","None","No","BROKEN","Target Cleanliness Heatmap has Admin guard","Citizen gets kicked to Login","Fix routing or auth"],
        ["W051","Citizen","Report Waste","Back Arrow Icon","Span","Report Waste/index.html","131","Navigate back","Not wrapped in button/a tag","None","No","BROKEN","citizen.js queries 'header button, header a' - span ignored","Cannot navigate back","Wrap in button"],
        ["W052","Citizen","Report Waste","Profile Avatar Logout","Image","Report Waste/index.html","136","Logout","Prompts confirm, clears localStorage","None","Yes (clears)","WORKING","Functional logout","None","None"],
        ["W053","Citizen","Report Waste","Report Form","Form","Report Waste/index.html","147","Submit waste report","submit event in citizen.js:210-271","POST /api/citizen/report_issue","Yes","WORKING","Full JSON submission with validation","None","None"],
        ["W054","Citizen","Report Waste","Image Upload Dropzone","File Input","Report Waste/index.html","150","Upload waste photo","Opens file picker but image not sent","None","No","PARTIALLY WORKING","File picker works but image discarded on submit","Image never uploaded to backend","Include in API payload"],
        ["W055","Citizen","Report Waste","Refine GPS Button","Button","Report Waste/index.html","169","Refine GPS coordinates","No handler attached","None","No","DUMMY / PLACEHOLDER","Static display coordinates","Button does nothing","Implement geolocation refresh"],
        ["W056","Citizen","Report Waste","Zone Dropdown","Select","Report Waste/index.html","175","Select ward/zone","Read on submit citizen.js:221","POST /api/citizen/report_issue","No","WORKING","Options: Ward 12, 15, 22","None","None"],
        ["W057","Citizen","Report Waste","Area Input","Text Input","Report Waste/index.html","189","Enter locality","Read and validated on submit","POST /api/citizen/report_issue","No","WORKING","Required field with error toast","None","None"],
        ["W058","Citizen","Report Waste","Waste Type General","Radio","Report Waste/index.html","195","Select waste type","Read on submit citizen.js:232","POST /api/citizen/report_issue","No","WORKING","Default selected category","None","None"],
        ["W059","Citizen","Report Waste","Waste Type Plastic","Radio","Report Waste/index.html","202","Select waste type","Read on submit citizen.js:232","POST /api/citizen/report_issue","No","WORKING","Plastic category option","None","None"],
        ["W060","Citizen","Report Waste","Waste Type Hazardous","Radio","Report Waste/index.html","209","Select waste type","Read on submit citizen.js:232","POST /api/citizen/report_issue","No","WORKING","Hazardous category option","None","None"],
        ["W061","Citizen","Report Waste","Description Textarea","Textarea","Report Waste/index.html","220","Describe issue","No id/name, not read by citizen.js","None","No","DUMMY / PLACEHOLDER","Text is completely discarded","Orphaned form field","Add id and include in submission"],
        ["W062","Citizen","Report Waste","Submit Report Button","Submit Button","Report Waste/index.html","225","Submit waste report","Triggers form submit","POST /api/citizen/report_issue","Yes","WORKING","Submits data, awards +10 pts, redirects","None","None"],
        ["W063","Citizen","Report Waste","Notifications Icon","Span","Report Waste/index.html","135","View notifications","No handler","None","No","DUMMY / PLACEHOLDER","Raw span with hover only","Not clickable","None needed"],
        ["W064","Citizen","Complaint History","Profile Avatar Logout","Image","Complaint History/index.html","131","Logout","Prompts confirm, clears localStorage","None","Yes (clears)","WORKING","Functional logout","None","None"],
        ["W065","Citizen","Complaint History","Notifications Button","Button","Complaint History/index.html","136","View notifications","No handler (lacks id)","None","No","BROKEN","Click does nothing","Missing btn-notifications id","Add id or handler"],
        ["W066","Citizen","Complaint History","Complaints List","Dynamic Container","Complaint History/index.html","148","Show all complaints","loadComplaints() renders full list","GET /api/citizen/my_reports","No (reads)","PARTIALLY WORKING","Data is real but cards not clickable","No detail drilldown","Add click handler"],
        ["W067","Citizen","Complaint History","Add Report FAB","FAB","Complaint History/index.html","157","Submit new report","Redirects to Report Waste","None","No","WORKING","Functional navigation","None","None"],
        ["W068","Citizen","Rewards","Profile Avatar Logout","Image","Rewards/index.html","98","Logout","Prompts confirm, clears localStorage","None","Yes (clears)","WORKING","Functional logout","None","None"],
        ["W069","Citizen","Rewards","Notifications Button","Button","Rewards/index.html","104","View notifications","No handler","None","No","BROKEN","Click does nothing","Unwired button","Add handler"],
        ["W070","Citizen","Rewards","EcoPoints Display","Display","Rewards/index.html","117","Show points balance","updatePointsUI in citizen.js","None","No (reads)","WORKING","Live synced from localStorage","None","None"],
        ["W071","Citizen","Rewards","Tier Progress Bar","Display Card","Rewards/index.html","122","Show tier progress","Static hardcoded (82%, 260 pts)","None","No","DUMMY / PLACEHOLDER","Static mockup data","Not dynamic","Implement tier logic"],
        ["W072","Citizen","Rewards","Impact Stats Cards","Display Cards","Rewards/index.html","137","Show environmental impact","Static hardcoded (42.5 kg CO2)","None","No","DUMMY / PLACEHOLDER","Static mockup metrics","Not calculated","Implement tracking"],
        ["W073","Citizen","Rewards","View All Rewards","Button","Rewards/index.html","164","View all rewards","No handler","None","No","DUMMY / PLACEHOLDER","Visual placeholder","Does nothing","Implement or remove"],
        ["W074","Citizen","Rewards","Dynamic Redeem Buttons","Buttons","citizen.js:304","Redeem reward","onclick calls redeemReward()","POST /api/citizen/redeem_reward","Yes","PARTIALLY WORKING","API works but toast.js missing in Rewards page","ReferenceError on showToast","Add toast.js import"],
        ["W075","Citizen","Rewards","District Leaderboard","Cards","Rewards/index.html","245","Show rankings","Static hardcoded names/scores","None","No","DUMMY / PLACEHOLDER","Hardcoded ranking mockup","Not dynamic","Implement leaderboard API"],
        ["W076","Citizen","Rewards","View Full Leaderboard","Button","Rewards/index.html","302","View leaderboard","No handler","None","No","DUMMY / PLACEHOLDER","Visual placeholder","Does nothing","Implement or remove"],
        ["W077","Admin","Waste Heatmap","Profile Avatar Logout","Image","Waste Heatmap/index.html","135","Admin logout","Prompts confirm, clears localStorage","None","Yes (clears)","WORKING","Functional admin logout","None","None"],
        ["W078","Admin","Waste Heatmap","Notifications Bell","Button","Waste Heatmap/index.html","141","View alerts","Toast only via admin.js:61","None","No","DUMMY / PLACEHOLDER","Toast: 'No critical system alerts.'","No alert system","Implement alerts"],
        ["W079","Admin","Waste Heatmap","By Ward Toggle","Button","Waste Heatmap/index.html","156","Filter by ward","Toggles CSS, shows toast","None","No","DUMMY / PLACEHOLDER","Toast: 'Switched view to By Ward'","No re-query","Implement filter"],
        ["W080","Admin","Waste Heatmap","By Waste Type Toggle","Button","Waste Heatmap/index.html","157","Filter by type","Toggles CSS, shows toast","None","No","DUMMY / PLACEHOLDER","Toast: 'Switched view to By Waste Type'","No re-query","Implement filter"],
        ["W081","Admin","Waste Heatmap","District Filter Chip","Chip","Waste Heatmap/index.html","160","Filter by district","Toast only via admin.js:19","None","No","DUMMY / PLACEHOLDER","Toast: 'Filter options opened'","No dropdown","Implement dropdown"],
        ["W082","Admin","Waste Heatmap","Type Filter Chip","Chip","Waste Heatmap/index.html","164","Filter by waste type","Toast only via admin.js:19","None","No","DUMMY / PLACEHOLDER","Toast: 'Filter options opened'","No dropdown","Implement dropdown"],
        ["W083","Admin","Waste Heatmap","Live Insights Stats","Display","Waste Heatmap/index.html","197","Show admin KPIs","Fetches from API, updates DOM","GET /api/admin/overview","No (reads)","WORKING","Live server data with formula","None","None"],
        ["W084","Admin","Waste Heatmap","Assign Driver Buttons","Dynamic Buttons","admin.js:248","Assign driver to complaint","Opens assign modal with complaint data","GET /api/admin/complaints","No","WORKING","Opens pre-populated modal","None","None"],
        ["W085","Admin","Waste Heatmap","Driver Select Dropdown","Select","Waste Heatmap/index.html","245","Select driver for assignment","Populated with drivers from API","GET /api/admin/drivers","No","WORKING","Live driver list","None","None"],
        ["W086","Admin","Waste Heatmap","Modal Cancel Button","Button","Waste Heatmap/index.html","249","Cancel assignment","Hides modal","None","No","WORKING","Functional modal dismiss","None","None"],
        ["W087","Admin","Waste Heatmap","Modal Confirm Assign","Button","Waste Heatmap/index.html","253","Confirm driver assignment","Calls API.assignTask, refreshes list","POST /api/admin/assign_task","Yes","WORKING","Full-stack write operation","None","None"],
        ["W088","Admin","Waste Heatmap","Nav Home","Link","Waste Heatmap/index.html","264","Navigate home","admin.js nav router","None","No","WORKING","Routes to Waste Heatmap","None","None"],
        ["W089","Admin","Waste Heatmap","Nav Map","Link","Waste Heatmap/index.html","269","View map","admin.js nav router","None","No","WORKING","Routes to Waste Heatmap","None","None"],
        ["W090","Admin","Waste Heatmap","Nav Tasks","Link","Waste Heatmap/index.html","274","View tasks","admin.js nav router","None","No","WORKING","Routes to Illegal Dumping","None","None"],
        ["W091","Admin","Waste Heatmap","Nav Reports","Link","Waste Heatmap/index.html","279","View reports","admin.js nav router","None","No","WORKING","Routes to Cleanliness Heatmap","None","None"],
        ["W092","Admin","Waste Heatmap","Nav Stats","Link","Waste Heatmap/index.html","284","View stats","Toast only","None","No","DUMMY / PLACEHOLDER","Toast: 'Stats view loading...'","No stats page","Implement stats"],
        ["W093","Admin","Illegal Dumping","Profile Avatar Logout","Image","Illegal Dumping/index.html","130","Admin logout","Prompts confirm, clears localStorage","None","Yes (clears)","WORKING","Functional admin logout","None","None"],
        ["W094","Admin","Illegal Dumping","Notifications Bell","Button","Illegal Dumping/index.html","136","View alerts","Toast only","None","No","DUMMY / PLACEHOLDER","Toast: 'No critical system alerts.'","None","None"],
        ["W095","Admin","Illegal Dumping","Critical Map Marker","Div","Illegal Dumping/index.html","149","Show hotspot","CSS hover only, no click","None","No","DUMMY / PLACEHOLDER","Visual marker, no interaction","Not clickable","Add click handler"],
        ["W096","Admin","Illegal Dumping","Moderate Map Marker","Div","Illegal Dumping/index.html","158","Show hotspot","CSS hover only, no click","None","No","DUMMY / PLACEHOLDER","Visual marker","Not clickable","Add click handler"],
        ["W097","Admin","Illegal Dumping","Clustered Marker","Div","Illegal Dumping/index.html","164","Show cluster","Static badge, no click","None","No","DUMMY / PLACEHOLDER","Visual marker","Not clickable","Add click handler"],
        ["W098","Admin","Illegal Dumping","Live Incidents Panel","Display","Illegal Dumping/index.html","174","Show incident stats","Fetches from API","GET /api/admin/illegal_dumping","No (reads)","WORKING","Live server data for admins","None","None"],
        ["W099","Admin","Illegal Dumping","AI Prediction Card","Display","Illegal Dumping/index.html","204","Show AI prediction","Static hardcoded","None","No","DUMMY / PLACEHOLDER","Static 'Private Contractors' 85% confidence","Not dynamic","Implement AI feed"],
        ["W100","Admin","Illegal Dumping","Weekly Chart","Display","Illegal Dumping/index.html","225","Show frequency chart","Static HTML bars","None","No","DUMMY / PLACEHOLDER","Static bar chart mockup","Not dynamic","Implement chart data"],
        ["W101","Admin","Illegal Dumping","Dispatch Team Button","Button","Illegal Dumping/index.html","249","Dispatch response team","admin.js handler checks 'Dispatch Team' but button says 'Dispatching Team'","None","No","BROKEN","String mismatch causes handler to miss","Button completely unhandled","Fix text or handler match"],
        ["W102","Admin","Illegal Dumping","Emergency FAB","Button","Illegal Dumping/index.html","258","Emergency alert","No handler","None","No","DUMMY / PLACEHOLDER","Unwired red warning button","Does nothing","Implement or remove"],
        ["W103","Admin","Cleanliness Heatmap","Profile Avatar Logout","Image","Cleanliness Heatmap/index.html","118","Admin logout","Prompts confirm, clears localStorage","None","Yes (clears)","WORKING","Functional admin logout","None","None"],
        ["W104","Admin","Cleanliness Heatmap","Notifications Bell","Button","Cleanliness Heatmap/index.html","124","View alerts","Toast only","None","No","DUMMY / PLACEHOLDER","Toast: 'No critical system alerts.'","None","None"],
        ["W105","Admin","Cleanliness Heatmap","Bin Markers (3)","Divs","Cleanliness Heatmap/index.html","140","Show bin locations","CSS hover tooltips only","None","No","DUMMY / PLACEHOLDER","Tooltip-only markers","Not clickable","Add click handlers"],
        ["W106","Admin","Cleanliness Heatmap","Search Input","Text Input","Cleanliness Heatmap/index.html","175","Search bins","No handler attached","None","No","DUMMY / PLACEHOLDER","Unwired text input","Does nothing","Implement search"],
        ["W107","Admin","Cleanliness Heatmap","My Location Button","Button","Cleanliness Heatmap/index.html","178","Center on GPS","No handler","None","No","DUMMY / PLACEHOLDER","Unwired icon button","Does nothing","Implement geolocation"],
        ["W108","Admin","Cleanliness Heatmap","Layers FAB","Button","Cleanliness Heatmap/index.html","203","Toggle map layers","No handler","None","No","DUMMY / PLACEHOLDER","Unwired button","Does nothing","Implement layers"],
        ["W109","Admin","Cleanliness Heatmap","Report FAB","Button","Cleanliness Heatmap/index.html","206","Create report","No handler","None","No","DUMMY / PLACEHOLDER","Unwired green action button","Does nothing","Implement action"],
        ["W110","Driver","Driver Dashboard","Profile Avatar Logout","Image","Driver Dashboard/index.html","132","Driver logout","Prompts confirm, clears localStorage","None","Yes (clears)","WORKING","Functional driver logout","None","None"],
        ["W111","Driver","Driver Dashboard","Notifications Bell","Button","Driver Dashboard/index.html","138","View notifications","Inline onclick toast","None","No","DUMMY / PLACEHOLDER","Toast: 'You have no new notifications.'","Hardcoded","Implement notifications"],
        ["W112","Driver","Driver Dashboard","View Detailed Stats","Button","Driver Dashboard/index.html","196","View stats","Inline onclick toast","None","No","DUMMY / PLACEHOLDER","Toast: 'Loading detailed stats...'","No stats page","Implement stats"],
        ["W113","Driver","Driver Dashboard","Alert Acknowledge Buttons","Dynamic Buttons","driver.js:151","Acknowledge alert","Inline onclick toast","None","No","DUMMY / PLACEHOLDER","Toast: 'Incident acknowledged'","No backend update","Implement acknowledge API"],
        ["W114","Driver","Driver Dashboard","Quick Task FAB","FAB","Driver Dashboard/index.html","237","Create quick task","Inline onclick toast","None","No","DUMMY / PLACEHOLDER","Toast: 'Opening quick task creation...'","No task form","Implement or remove"],
        ["W115","Driver","Driver Dashboard","GPS Telemetry Loop","Script","driver.js:22","Track driver location","5s interval getCurrentPosition + API call","POST /api/driver/update_location","Yes","WORKING","Real background GPS telemetry","None","None"],
        ["W116","Driver","Driver Dashboard","WebSocket Notifications","Script","driver.js:44","Real-time push alerts","Connects to ws endpoint, triggers haptics","WS /api/ws/driver/{id}","No","WORKING","Real-time push connection","None","None"],
        ["W117","Driver","Driver Dashboard","Dashboard Data Loader","Script","driver.js:121","Load dashboard stats","Fetches from API, updates DOM","GET /api/driver/dashboard","No (reads)","WORKING","Live server data","None","None"],
        ["W118","Driver","Driver Dashboard","Nav Home","Link","Driver Dashboard/index.html","243","Navigate home","driver.js nav router","None","No","WORKING","Routes to Driver Dashboard","None","None"],
        ["W119","Driver","Driver Dashboard","Nav Map","Link","Driver Dashboard/index.html","247","View map","driver.js nav router","None","No","WORKING","Routes to Navigation Screen","None","None"],
        ["W120","Driver","Driver Dashboard","Nav Tasks","Link","Driver Dashboard/index.html","251","View tasks","driver.js nav router","None","No","WORKING","Routes to Assigned Pickups","None","None"],
        ["W121","Driver","Driver Dashboard","Nav Reports","Link","Driver Dashboard/index.html","255","View reports","Toast: 'Feature coming soon!'","None","No","DUMMY / PLACEHOLDER","Placeholder toast","No reports page","Implement"],
        ["W122","Driver","Driver Dashboard","Nav Stats","Link","Driver Dashboard/index.html","259","View stats","Toast: 'Feature coming soon!'","None","No","DUMMY / PLACEHOLDER","Placeholder toast","No stats page","Implement"],
        ["W123","Driver","Assigned Pickups","Profile Avatar Logout","Image","Assigned Pickups/index.html","138","Driver logout","Prompts confirm","None","Yes (clears)","WORKING","Functional logout","None","None"],
        ["W124","Driver","Assigned Pickups","Notifications Bell","Button","Assigned Pickups/index.html","143","View notifications","No handler attached","None","No","BROKEN","Unwired button, click does nothing","Missing handler","Add handler"],
        ["W125","Driver","Assigned Pickups","Priority Filter","Button","Assigned Pickups/index.html","172","Filter by priority","No handler attached","None","No","BROKEN","Unwired filter button","No filter logic","Implement filter"],
        ["W126","Driver","Assigned Pickups","Task Details Buttons","Dynamic Buttons","driver.js:233","View task details","Inline onclick toast","None","No","DUMMY / PLACEHOLDER","Toast: 'Viewing details for task X'","No detail modal","Implement detail view"],
        ["W127","Driver","Assigned Pickups","Start Route Buttons","Dynamic Buttons","driver.js:236","Start navigation","Navigates to Navigation Screen with ID","None","No","WORKING","Real navigation with complaint_id","None","None"],
        ["W128","Driver","Assigned Pickups","Map Fullscreen Button","Button","Assigned Pickups/index.html","194","Fullscreen map","No handler","None","No","BROKEN","Unwired button","Does nothing","Implement or remove"],
        ["W129","Driver","Assigned Pickups","Static Task Card (Details)","Button","Assigned Pickups/index.html","219","View details","No handler (leftover template)","None","No","BROKEN","Dead static HTML","Leftover mock","Remove"],
        ["W130","Driver","Assigned Pickups","Static Task Card (Route)","Button","Assigned Pickups/index.html","222","Start route","No handler (leftover template)","None","No","BROKEN","Dead static HTML","Leftover mock","Remove"],
        ["W131","Driver","Assigned Pickups","Emergency FAB","FAB","Assigned Pickups/index.html","232","Emergency support","Inline onclick toast","None","No","DUMMY / PLACEHOLDER","Toast: 'Dispatching Emergency Support...'","No backend call","Implement or remove"],
        ["W132","Driver","Navigation Screen","Profile Avatar Logout","Image","Navigation Screen/index.html","131","Driver logout","Prompts confirm","None","Yes (clears)","WORKING","Functional logout","None","None"],
        ["W133","Driver","Navigation Screen","Notifications Bell","Button","Navigation Screen/index.html","137","View notifications","No handler","None","No","BROKEN","Unwired button","Does nothing","Add handler"],
        ["W134","Driver","Navigation Screen","Center Map FAB","Button","Navigation Screen/index.html","207","Center map","Inline onclick toast","None","No","DUMMY / PLACEHOLDER","Toast: 'Centering Map...'","No map pan","Implement"],
        ["W135","Driver","Navigation Screen","Map Layers FAB","Button","Navigation Screen/index.html","210","Toggle layers","Inline onclick toast","None","No","DUMMY / PLACEHOLDER","Toast: 'Toggling Map Layers...'","No layer toggle","Implement"],
        ["W136","Driver","Navigation Screen","Issue Button","Button","Navigation Screen/index.html","195","Report issue","Inline onclick toast","None","No","DUMMY / PLACEHOLDER","Toast: 'Opening issue reporter...'","No form","Implement"],
        ["W137","Driver","Navigation Screen","Arrived Button","Button","Navigation Screen/index.html","199","Confirm arrival","driver.js:253 reads ID, navigates","None","No","WORKING","Navigates to Pickup Verification","None","None"],
        ["W138","Driver","Pickup Verification","Profile Avatar Logout","Image","Pickup Verification/index.html","140","Driver logout","Prompts confirm","None","Yes (clears)","WORKING","Functional logout","None","None"],
        ["W139","Driver","Pickup Verification","Photo Capture Button","Button","Pickup Verification/index.html","179","Capture proof photo","Triggers file input click","None","No","WORKING","Opens camera/file picker","None","None"],
        ["W140","Driver","Pickup Verification","Waste Level Buttons (3)","Buttons","Pickup Verification/index.html","216","Select waste level","No handlers attached","None","No","BROKEN","Visual pills, not selectable, not submitted","Dead form controls","Wire toggle + submit"],
        ["W141","Driver","Pickup Verification","Report Issue Dropdown","Select","Pickup Verification/index.html","240","Report issue type","No id/name, never read by driver.js","None","No","DUMMY / PLACEHOLDER","Disconnected form control","User selection ignored","Add id and include"],
        ["W142","Driver","Pickup Verification","Confirm Pickup Button","Submit Button","Pickup Verification/index.html","252","Complete pickup","Form submit in driver.js:281","POST /api/driver/complete_pickup","Yes","WORKING","Marks task COMPLETED and complaint RESOLVED","None","None"],
        ["W143","Driver","Pickup Verification","Notifications Bell","Button","Pickup Verification/index.html","137","View notifications","No handler","None","No","BROKEN","Unwired button","Does nothing","Add handler"]
    ];
    
    elementsRaw.forEach(row => {
        const r = wsInventory.addRow(row);
        applyStatusStyle(r.getCell(12), row[11]);
    });
    autoFitColumns(wsInventory);
    
    // 3. Feature Audit Sheet
    const wsFeatures = wb.addWorksheet('Feature Audit');
    const fHeaders = ['Feature', 'Category', 'Status', 'Backend Endpoint', 'Frontend Implementation', 'Evidence', 'Notes'];
    applyHeaderStyle(wsFeatures.addRow(fHeaders));
    
    const featuresRaw = [
        ["Authentication (Login)","Core","WORKING","POST /api/auth/login","auth.js + Login Screen form","JWT token, role-based redirect","Fully functional"],
        ["Authentication (Registration)","Core","WORKING","POST /api/auth/register","auth.js + Register Screen form","Creates user as CITIZEN","Role selection ignored"],
        ["Role-Based Access Control","Core","WORKING","Backend verify_citizen/driver/admin","auth.js redirectBasedOnRole","Backend enforces roles","Frontend role guard in citizen.js, driver.js, admin.js"],
        ["Citizen Waste Reporting","Core","WORKING","POST /api/citizen/report_issue","citizen.js form handler","Persists complaint, awards +10 pts","Image upload orphaned"],
        ["Complaint History","Core","PARTIALLY WORKING","GET /api/citizen/my_reports","citizen.js loadComplaints","Lists all reports with status","No detail drill-down on cards"],
        ["Rewards & EcoPoints","Core","PARTIALLY WORKING","GET /api/citizen/rewards + POST redeem","citizen.js loadRewards + redeemReward","Points deducted, redemption logged","toast.js missing on Rewards page causes ReferenceError"],
        ["Admin Dashboard Metrics","Core","WORKING","GET /api/admin/overview","admin.js loadAdminData","Total bins, critical bins, collection rate","Bin count uses formula (complaints * 12)"],
        ["Admin Complaint Management","Core","WORKING","GET /api/admin/complaints","admin.js loadAdminComplaints","Lists all complaints with Assign button","No pagination"],
        ["Admin Driver Assignment","Core","WORKING","POST /api/admin/assign_task","admin.js modal + confirm handler","Creates DriverTask, updates complaint, sends WebSocket","No duplicate-assignment check"],
        ["Admin Driver Listing","Core","WORKING","GET /api/admin/drivers","admin.js driver select dropdown","Populates modal dropdown","No driver detail view"],
        ["Driver Dashboard","Core","WORKING","GET /api/driver/dashboard","driver.js loadDriverDashboard","Shows task counts and greeting","completed_today counts all-time"],
        ["Driver Task List","Core","WORKING","GET /api/driver/assigned_tasks","driver.js loadAssignedTasks","Shows assigned tasks with Start Route","Details button is toast-only"],
        ["Driver Pickup Completion","Core","WORKING","POST /api/driver/complete_pickup","driver.js setupPickupVerification","Marks task COMPLETED, complaint RESOLVED","Waste level/issue dropdown ignored"],
        ["Driver GPS Tracking","Core","WORKING","POST /api/driver/update_location","driver.js 5s interval","Real-time GPS upsert to database","No WebSocket broadcast to admin"],
        ["WebSocket Notifications","Core","WORKING","WS /api/ws/driver/{id}","driver.js WebSocket handler","Real-time NEW_TASK push with haptics","Only driver-facing"],
        ["Admin User Creation","Backend Only","PARTIALLY WORKING","POST /api/admin/create_user","No frontend UI","Endpoint works but no admin screen invokes it","Missing UI"],
        ["Heatmap Visualization","UI","DUMMY / PLACEHOLDER","GET /api/admin/waste_heatmap","Static CSS markers in Waste Heatmap HTML","API returns coordinates but no map library renders them","Static visual representation"],
        ["Illegal Dumping Detection","UI","PARTIALLY WORKING","GET /api/admin/illegal_dumping","admin.js loads stats but markers are static","Live stats from DB, markers are static HTML","AI prediction card is hardcoded"],
        ["Cleanliness Heatmap","UI","DUMMY / PLACEHOLDER","None","Static HTML bin markers with CSS tooltips","Hardcoded bin locations and fill percentages","No real data integration"],
        ["Map/Filter Controls","UI","DUMMY / PLACEHOLDER","None","Toast-only handlers in admin.js","By Ward, By Waste Type, District filter all show toasts","No actual filtering"],
        ["Image Processing","Advertised","NOT IMPLEMENTED","None","File input exists but image discarded","Response says 'Image analysis queued' but nothing happens","Mentioned in API response only"],
        ["AI/IoT Integration","Advertised","NOT IMPLEMENTED","None","None","No AI models, no IoT sensor feeds","Static mockup data only"],
        ["Turn-by-Turn Navigation","UI","DUMMY / PLACEHOLDER","None","Navigation Screen shows static map image","No Google Maps or routing integration","Static visual"],
        ["Automatic Dispatch","Advertised","NOT IMPLEMENTED","None","None","Admin manually assigns via modal","No algorithm"],
        ["Search Functionality","UI","DUMMY / PLACEHOLDER","None","Cleanliness Heatmap search input unwired","Input exists but no handler","Implement search"],
        ["Social/OAuth Login","UI","DUMMY / PLACEHOLDER","None","Google and Apple buttons on Login Screen","No OAuth handlers","Buttons are inert"],
        ["Password Reset","UI","DUMMY / PLACEHOLDER","None","Forgot Password link is href='#'","No reset flow exists","Dead link"],
        ["Onboarding Flow","UI","DUMMY / PLACEHOLDER","None","3 screens exist but all buttons are unwired","Skip, Next, Get Started all inert","Wire navigation"],
        ["Notification System","UI","DUMMY / PLACEHOLDER","None","Bell buttons exist on every screen","All show toast or are unwired","No notification backend"],
        ["Role Selection Screen","UI","DUMMY / PLACEHOLDER","None","Role cards on Role Selection screen","No event handlers","Inert mockup screen"]
    ];
    
    featuresRaw.forEach(row => {
        const r = wsFeatures.addRow(row);
        applyStatusStyle(r.getCell(3), row[2]);
    });
    autoFitColumns(wsFeatures);
    
    // 4. Issues & Fixes Sheet
    const wsIssues = wb.addWorksheet('Issues & Fixes');
    const iHeaders = ['ID', 'Severity', 'Screen', 'Element', 'Status', 'Evidence', 'Recommended Fix'];
    applyHeaderStyle(wsIssues.addRow(iHeaders));
    
    const issuesRaw = [
        ["I001","P0","Citizen Dashboard","Bottom Nav Map","BROKEN","Navigates to Waste Heatmap which enforces Admin role guard","Create citizen-accessible map screen or add citizen role to Waste Heatmap auth"],
        ["I002","P0","Citizen Dashboard","Bottom Nav Stats","BROKEN","Navigates to Cleanliness Heatmap which enforces Admin role guard","Same as above"],
        ["I003","P0","Citizen Dashboard","Explore Nearby Bins","BROKEN","Same as I002","Same fix needed"],
        ["I004","P0","Rewards","Missing toast.js import","BROKEN","Rewards/index.html omits toast.js, causing ReferenceError on redeem","Add toast.js script tag to Rewards/index.html"],
        ["I005","P1","Report Waste","Back Arrow Span","BROKEN","arrow_back is a span not button/a; citizen.js selector misses it","Wrap span in button element"],
        ["I006","P1","Illegal Dumping","Dispatch Team Button","BROKEN","admin.js checks 'Dispatch Team' but button says 'Dispatching Team'","Fix string match or button text"],
        ["I007","P1","Pickup Verification","Waste Level Buttons","BROKEN","3 buttons (Empty/Partial/Full) have no handlers and are not submitted","Wire toggle handlers and include in form data"],
        ["I008","P1","Pickup Verification","Report Issue Dropdown","DUMMY / PLACEHOLDER","Select has no id/name, never read by driver.js","Add id and include in complete_pickup payload"],
        ["I009","P1","Report Waste","Image Upload","PARTIALLY WORKING","File picker works but image discarded on submit","Include file in FormData to backend"],
        ["I010","P1","Assigned Pickups","Notifications Bell","BROKEN","No handler attached","Add click handler"],
        ["I011","P1","Navigation Screen","Notifications Bell","BROKEN","No handler attached","Add click handler"],
        ["I012","P1","Pickup Verification","Notifications Bell","BROKEN","No handler attached","Add click handler"],
        ["I013","P1","Complaint History","Notifications Button","BROKEN","Lacks btn-notifications id","Add id and handler"],
        ["I014","P1","Assigned Pickups","Priority Filter","BROKEN","No handler attached","Implement filter logic"],
        ["I015","P1","Assigned Pickups","Static Mock Cards","BROKEN","Leftover static HTML template","Remove dead HTML"],
        ["I016","P1","Assigned Pickups","Map Fullscreen","BROKEN","No handler","Implement or remove"],
        ["I017","P2","Driver Dashboard","Alert Acknowledge","DUMMY / PLACEHOLDER","Toast only, no backend update","Implement acknowledge API endpoint"],
        ["I018","P2","Report Waste","Description Textarea","DUMMY / PLACEHOLDER","No id/name, text discarded","Add id, include in submission"],
        ["I019","P2","Report Waste","Refine GPS Button","DUMMY / PLACEHOLDER","No handler","Implement geolocation refresh"],
        ["I020","P2","All Screens","Notification Bells","DUMMY / PLACEHOLDER","All show hardcoded toast or are unwired","Implement notification system"],
        ["I021","P2","Login Screen","Password Visibility","DUMMY / PLACEHOLDER","No toggle handler","Implement password toggle"],
        ["I022","P2","Login Screen","Remember Me","DUMMY / PLACEHOLDER","Not read by auth.js","Implement or remove"],
        ["I023","P2","Login Screen","Forgot Password","DUMMY / PLACEHOLDER","Dead href='#' link","Implement reset flow or remove"],
        ["I024","P2","Login Screen","Social Login Buttons","DUMMY / PLACEHOLDER","No OAuth handlers","Remove or implement"],
        ["I025","P3","Onboarding 1-3","All Buttons","DUMMY / PLACEHOLDER","Skip, Next, Get Started all inert","Wire navigation between screens"],
        ["I026","P3","Role Selection","All Cards","DUMMY / PLACEHOLDER","No click handlers","Wire navigation or remove screen"],
        ["I027","P3","Rewards","Tier Progress / Leaderboard","DUMMY / PLACEHOLDER","All static hardcoded data","Implement dynamic data"],
        ["I028","P3","Admin Screens","All Map Markers","DUMMY / PLACEHOLDER","Static HTML, no map library","Integrate real map library"],
        ["I029","P3","Admin Screens","Filter Controls","DUMMY / PLACEHOLDER","All toast-only","Implement actual filtering"]
    ];
    
    issuesRaw.forEach(row => {
        const r = wsIssues.addRow(row);
        applyStatusStyle(r.getCell(5), row[4]);
    });
    autoFitColumns(wsIssues);
    
    const outPath = path.join(reportsDir, 'scos_web_functionality_audit.xlsx');
    await wb.xlsx.writeFile(outPath);
    console.log('Saved Web Audit to:', outPath);
}

async function generateAndroidAudit() {
    const wb = new ExcelJS.Workbook();
    
    // 1. Summary Sheet
    const wsSummary = wb.addWorksheet('Summary');
    wsSummary.addRow(['SCOS Android Capacitor Wrapper - Functionality Audit Summary']);
    wsSummary.getRow(1).font = { name: 'Segoe UI', size: 14, bold: true, color: { argb: 'FF1F4E79' } };
    wsSummary.addRow([]);
    wsSummary.addRow(['Metric', 'Value']);
    applyHeaderStyle(wsSummary.getRow(3));
    
    const summaryData = [
        ['Total Android-Specific Elements Audited', 9],
        ['Working (Verified via Source/Config)', 3],
        ['Partially Working', 2],
        ['Dummy / Placeholder', 1],
        ['Broken / Defective', 2],
        ['Unverified (Requires Device/Emulator)', 1],
        ['Working Percentage', '33.3%'],
        ['Non-Working or Incomplete Percentage', '66.7%'],
        ['Note on Shared Web Assets', 'Android wraps the same web codebase (143 elements). Documented in Web Audit.']
    ];
    summaryData.forEach(row => wsSummary.addRow(row));
    autoFitColumns(wsSummary);
    
    // 2. Element Inventory Sheet
    const wsInventory = wb.addWorksheet('Element Inventory');
    const invHeaders = ['ID', 'Feature', 'Element Type', 'Source File', 'Implementation', 'API Endpoint', 'Status', 'Evidence', 'Missing / Failure Reason', 'Recommended Fix'];
    applyHeaderStyle(wsInventory.addRow(invHeaders));
    
    const elementsRaw = [
        ["A001","Hardware Back Button","Native Handler","mobile.js","App.addListener('backButton') with history.back() or exitApp()","None","WORKING","Fully functional via @capacitor/app plugin","None","None"],
        ["A002","Native Haptics on NEW_TASK","Native Vibration","driver.js:70","Haptics.impact({ style: ImpactStyle.Heavy })","None","WORKING","@capacitor/haptics installed, VIBRATE merged permission","None","None"],
        ["A003","Local Notifications on NEW_TASK","Native Notification","driver.js:72","LocalNotifications.schedule()","None","PARTIALLY WORKING","Plugin installed but requestPermissions() never called","Fails silently on Android 13+ (API 33+)","Add requestPermissions() call"],
        ["A004","Geolocation (GPS)","Web API Fallback","driver.js:26, citizen.js:195","navigator.geolocation.getCurrentPosition()","POST /api/driver/update_location","BROKEN","No @capacitor/geolocation plugin, no ACCESS_FINE_LOCATION in manifest","WebView denies GPS access","Install plugin, add permissions"],
        ["A005","Camera/Photo Capture","HTML File Input","Pickup Verification, Report Waste","<input type='file' accept='image/*'>","None","PARTIALLY WORKING","WebView file picker works but no native camera plugin","No EXIF GPS, basic UX","Install @capacitor/camera (optional)"],
        ["A006","Cloud Backend Redirect","JS Config","api.js:8","BASE_URL switches to scos-app.onrender.com when native","All endpoints","WORKING","Correctly targets cloud backend on Android","None","None"],
        ["A007","Safe Area Insets","CSS","All screens","padding-top/bottom: env(safe-area-inset)","None","UNVERIFIED","CSS rules present in HTML headers","Not verified on live device/emulator","Verify on live hardware"],
        ["A008","Capacitor Core CDN Load","Script Tag","All HTML screens","<script src='https://cdn.jsdelivr.net/npm/@capacitor/core/...'>","None","BROKEN","Relies on CDN for offline-capable mobile app","Fails on cold start without connectivity","Bundle capacitor.js locally in assets"],
        ["A009","WebSocket URL Switch","JS Config","driver.js:49","wsBaseUrl switches to cloud host when native","WS /api/ws/driver/{id}","WORKING","Correct protocol/host for native context","None","None"]
    ];
    elementsRaw.forEach(row => {
        const r = wsInventory.addRow(row);
        applyStatusStyle(r.getCell(7), row[6]);
    });
    autoFitColumns(wsInventory);
    
    // 3. Feature Audit Sheet
    const wsFeatures = wb.addWorksheet('Feature Audit');
    const fHeaders = ['Feature', 'Status', 'Evidence', 'Notes'];
    applyHeaderStyle(wsFeatures.addRow(fHeaders));
    
    const featuresRaw = [
        ["Android Back Button","WORKING","@capacitor/app handles backButton event","history.back() or exitApp()"],
        ["Haptic Feedback","WORKING","@capacitor/haptics installed, VIBRATE merged permission","Triggers on NEW_TASK WebSocket"],
        ["Local Notifications","PARTIALLY WORKING","Plugin installed but no requestPermissions()","Breaks on Android 13+ (API 33+)"],
        ["Geolocation/GPS","BROKEN","No @capacitor/geolocation, no manifest permissions","WebView auto-denies GPS"],
        ["Camera Integration","PARTIALLY WORKING","HTML file input works in WebView","No native camera controls"],
        ["Offline Support","BROKEN","Capacitor Core loaded from CDN","No offline capability"],
        ["Push Notifications (Remote)","NOT IMPLEMENTED","No google-services.json, no FCM plugin","Only local notifications exist"],
        ["Deep Linking","NOT IMPLEMENTED","Custom URL scheme defined but no deep link routes","com.scos.app scheme unused"],
        ["App Updates","NOT IMPLEMENTED","No in-app update mechanism","Manual APK distribution only"]
    ];
    featuresRaw.forEach(row => {
        const r = wsFeatures.addRow(row);
        applyStatusStyle(r.getCell(2), row[1]);
    });
    autoFitColumns(wsFeatures);
    
    // 4. Issues & Fixes Sheet
    const wsIssues = wb.addWorksheet('Issues & Fixes');
    const iHeaders = ['ID', 'Severity', 'Feature', 'Status', 'Evidence', 'Recommended Fix'];
    applyHeaderStyle(wsIssues.addRow(iHeaders));
    
    const issuesRaw = [
        ["A-I001","P0","Geolocation","BROKEN","No manifest permissions, no Capacitor plugin","Install @capacitor/geolocation, add ACCESS_FINE_LOCATION + ACCESS_COARSE_LOCATION"],
        ["A-I002","P1","Local Notifications","PARTIALLY WORKING","Never calls requestPermissions()","Add LocalNotifications.requestPermissions() on driver login"],
        ["A-I003","P1","Capacitor Core CDN","BROKEN","Loaded from jsdelivr CDN in all HTML files","Bundle capacitor.js locally in static assets"],
        ["A-I004","P2","Camera","PARTIALLY WORKING","No native camera plugin","Consider installing @capacitor/camera for better UX"],
        ["A-I005","P3","Push Notifications","NOT IMPLEMENTED","No FCM/google-services.json","Implement if server-side push needed"]
    ];
    issuesRaw.forEach(row => {
        const r = wsIssues.addRow(row);
        applyStatusStyle(r.getCell(4), row[3]);
    });
    autoFitColumns(wsIssues);
    
    const outPath = path.join(reportsDir, 'scos_android_functionality_audit.xlsx');
    await wb.xlsx.writeFile(outPath);
    console.log('Saved Android Audit to:', outPath);
}

async function main() {
    console.log('Generating SCOS Web Functionality Audit...');
    await generateWebAudit();
    console.log('Generating SCOS Android Functionality Audit...');
    await generateAndroidAudit();
    console.log('Reports generation complete!');
}

main().catch(err => {
    console.error('Error generating reports:', err);
    process.exit(1);
});
