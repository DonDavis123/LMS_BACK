/**
 * LeadPulse mail relay — Google Apps Script web app.
 * Deploy while signed in as leadpulse123@gmail.com; mail is sent from it.
 *
 * Backend contract (see HttpEmailService):
 *   POST <web app URL>?key=<MAIL_SECRET>   Content-Type: application/json
 *   { "to", "subject", "text", "html", "reset_link" }
 *
 * Apps Script cannot read request headers, so the shared secret travels
 * in the query string (?key=...), not in an Authorization header.
 * Always answers JSON: {"ok": true} or {"ok": false, "error": "..."}.
 */

var SENDER_NAME = "LeadPulse";

function doPost(e) {
  try {
    var secret = PropertiesService.getScriptProperties().getProperty("MAIL_SECRET");

    if (!secret || !e.parameter || e.parameter.key !== secret) {
      return reply_({ ok: false, error: "unauthorized" });
    }

    var data = JSON.parse(e.postData.contents);

    if (!data.to || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.to) || !data.subject) {
      return reply_({ ok: false, error: "valid 'to' and 'subject' are required" });
    }

    GmailApp.sendEmail(data.to, data.subject, data.text || "", {
      htmlBody: data.html || undefined,
      name: SENDER_NAME,
    });

    return reply_({ ok: true });
  } catch (err) {
    return reply_({ ok: false, error: String(err) });
  }
}

function reply_(body) {
  return ContentService
    .createTextOutput(JSON.stringify(body))
    .setMimeType(ContentService.MimeType.JSON);
}

/** Run once from the editor to grant the Gmail permission. */
function authorizeOnce() {
  GmailApp.sendEmail(
    Session.getActiveUser().getEmail(),
    "LeadPulse mailer authorised",
    "The Gmail permission is granted."
  );
}
