<?php
// Optional PHP webhook that records inbound SMS to the same SQLite DB.
// Configure your server to accept Twilio POSTs to this script.
// Set DB_PATH to the path of polls.db (same file used by Python app).
$dbPath = __DIR__ . '/../polls.db';
if (!file_exists($dbPath)) {
    error_log("DB not found: $dbPath");
    http_response_code(500);
    echo "DB not found";
    exit;
}
$from = $_POST['From'] ?? '';
$body = $_POST['Body'] ?? '';
$to = $_POST['To'] ?? '';
$now = date('Y-m-d H:i:s');

try {
    $pdo = new PDO("sqlite:$dbPath");
    // find latest poll id
    $stmt = $pdo->query("SELECT id FROM polls ORDER BY created_at DESC LIMIT 1");
    $poll_id = $stmt->fetchColumn();
    $stmt = $pdo->prepare("INSERT INTO raw_messages (poll_id, from_number, to_number, body, received_at) VALUES (?, ?, ?, ?, ?)");
    $stmt->execute([$poll_id, $from, $to, $body, $now]);
    // very simple responder
    header("Content-Type: text/xml");
    echo "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<Response>\n  <Message>Thanks, we received your reply.</Message>\n</Response>";
} catch (Exception $e) {
    error_log("Webhook error: " . $e->getMessage());
    http_response_code(500);
    echo "Error";
}
