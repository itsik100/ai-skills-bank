/**
 * Scout reply trigger — מעיר את "סקאוט — טיפול בתשובות" ברגע שאיציק משיב למייל [סקאוט].
 *
 * התקנה (פעם אחת):
 * 1. script.google.com → New project → הדבק את הקובץ הזה.
 * 2. Project Settings (גלגל שיניים) → Script Properties → Add:
 *      SCOUT_FIRE_URL   = ה-URL מטריגר ה-API של ה-Routine
 *      SCOUT_FIRE_TOKEN = הטוקן (sk-ant-oat01-...)
 * 3. הרץ פעם אחת את setup() ואשר הרשאות (Gmail קריאה + גישה לרשת).
 *
 * מה הוא עושה: כל 5 דקות מחפש תשובות שלך (Re:) בשרשורי [סקאוט] מהיממה האחרונה.
 * לכל תשובה חדשה הוא מפעיל את ה-Routine פעם אחת, ומעביר רק את מזהה השרשור.
 * הוא לא קורא תוכן, לא שולח מיילים ולא משנה תוויות.
 */

const OWNER = 'itzikiluz28@gmail.com';
const PROCESSED_KEY = 'SCOUT_PROCESSED_IDS';
const MAX_PROCESSED = 300;

function setup() {
  ScriptApp.getProjectTriggers()
    .filter(t => t.getHandlerFunction() === 'checkScoutReplies')
    .forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('checkScoutReplies').timeBased().everyMinutes(5).create();
  // מסמן תשובות קיימות כמטופלות, כדי שההפעלה הראשונה לא תירה על עבר.
  markExistingAsProcessed_();
  Logger.log('Scout reply trigger installed (every 5 minutes).');
}

function checkScoutReplies() {
  const props = PropertiesService.getScriptProperties();
  const url = props.getProperty('SCOUT_FIRE_URL');
  const token = props.getProperty('SCOUT_FIRE_TOKEN');
  if (!url || !token) {
    Logger.log('Missing SCOUT_FIRE_URL or SCOUT_FIRE_TOKEN in Script Properties.');
    return;
  }

  const processed = loadProcessed_(props);
  const threads = GmailApp.search('subject:סקאוט from:me newer_than:1d', 0, 30);

  threads.forEach(thread => {
    const replies = thread.getMessages().filter(m => isOwnerReply_(m) && !processed.has(m.getId()));
    if (replies.length === 0) return;

    const ok = fire_(url, token, thread.getId());
    if (ok) replies.forEach(m => processed.add(m.getId()));
  });

  saveProcessed_(props, processed);
}

function isOwnerReply_(msg) {
  const fromOwner = msg.getFrom().toLowerCase().indexOf(OWNER) !== -1;
  const subject = msg.getSubject() || '';
  const isReply = /^\s*(re|תגובה|השב)\s*:/i.test(subject) && subject.indexOf('[סקאוט]') !== -1;
  return fromOwner && isReply && !msg.isDraft();
}

function fire_(url, token, threadId) {
  const res = UrlFetchApp.fetch(url, {
    method: 'post',
    contentType: 'application/json',
    headers: {
      'Authorization': 'Bearer ' + token,
      'anthropic-beta': 'experimental-cc-routine-2026-04-01',
      'anthropic-version': '2023-06-01'
    },
    payload: JSON.stringify({ text: 'threadId: ' + threadId }),
    muteHttpExceptions: true
  });
  const code = res.getResponseCode();
  Logger.log('Fire ' + threadId + ' → ' + code);
  return code >= 200 && code < 300;
}

function markExistingAsProcessed_() {
  const props = PropertiesService.getScriptProperties();
  const processed = loadProcessed_(props);
  GmailApp.search('subject:סקאוט from:me newer_than:7d', 0, 50).forEach(thread =>
    thread.getMessages().filter(isOwnerReply_).forEach(m => processed.add(m.getId()))
  );
  saveProcessed_(props, processed);
}

function loadProcessed_(props) {
  const raw = props.getProperty(PROCESSED_KEY);
  return new Set(raw ? JSON.parse(raw) : []);
}

function saveProcessed_(props, set) {
  const arr = Array.from(set).slice(-MAX_PROCESSED);
  props.setProperty(PROCESSED_KEY, JSON.stringify(arr));
}
