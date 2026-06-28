// Dashboard wires the shared cell-action controller with the persisted-results
// page configuration rendered by dashboard-viewer.js.
window.CytoCVResultsCellActions.init({
    pageConfig: window.CytoCVDashboardPageConfig || {},
});
