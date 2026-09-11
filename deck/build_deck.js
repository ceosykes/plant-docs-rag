// Three slides for stakeholders: the problem, why it exists, what we built. Few words.
const pptxgen = require("pptxgenjs");
const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10 x 5.625 in

const INK = "1F2933", MUTE = "5B6770", PURPLE = "6F42C1", RED = "C62828", BLUE = "1565C0", GREEN = "2E7D32", AMBER = "EF6C00", PANEL = "F3F4F6";
const H = { fontFace: "Cambria", bold: true, color: INK, isTextBox: true, margin: 0 };
const B = { fontFace: "Calibri", color: INK, isTextBox: true, margin: 0, valign: "top" };

function shelf(slide, x, y, color, name, what, dark) {
  slide.addShape(pres.ShapeType.roundRect, { x, y, w: 2.9, h: 0.95, fill: { color: dark ? "2B3743" : PANEL }, line: { color: dark ? "2B3743" : PANEL }, rectRadius: 0.08 });
  slide.addShape(pres.ShapeType.ellipse, { x: x + 0.18, y: y + 0.17, w: 0.26, h: 0.26, fill: { color }, line: { color } });
  slide.addText(name, { ...H, x: x + 0.58, y: y + 0.13, w: 2.2, h: 0.35, fontSize: 15, color: dark ? "FFFFFF" : INK });
  slide.addText(what, { ...B, x: x + 0.18, y: y + 0.52, w: 2.6, h: 0.4, fontSize: 11, color: dark ? "CADCFC" : MUTE });
}

// 1. The problem
{
  const s = pres.addSlide();
  s.background = { color: INK };
  s.addText("The problem", { ...B, x: 0.5, y: 0.5, w: 9, h: 0.35, fontSize: 14, color: "CADCFC" });
  s.addText("Employees bring their questions to their supervisor.", { ...H, x: 0.5, y: 1.0, w: 9, h: 0.55, fontSize: 26, color: "FFFFFF" });
  s.addText("The operator wants every answer the supervisor gives to be true, and a way to check that it is.", { ...H, x: 0.5, y: 1.7, w: 9, h: 1.2, fontSize: 26, color: "FFFFFF" });
  s.addText("The answers live in three kinds of documents", { ...B, x: 0.5, y: 3.55, w: 9, h: 0.3, fontSize: 12, color: "CADCFC" });
  shelf(s, 0.5, 3.95, RED, "Safety", "Lockout, guarding, PPE, noise, chemicals", true);
  shelf(s, 3.55, 3.95, BLUE, "Maintenance", "Pump, motor, belt, bearing and compressor manuals", true);
  shelf(s, 6.6, 3.95, GREEN, "Quality", "Sampling, calibration, validation, CGMP rules", true);
  s.addNotes("One idea on this slide: the operator wants true answers and a way to check them.");
}

// 2. Why the problem exists, and the hook
{
  const s = pres.addSlide();
  s.background = { color: "FFFFFF" };
  s.addText("Why it is hard today", { ...B, x: 0.5, y: 0.4, w: 9, h: 0.35, fontSize: 14, color: MUTE });
  s.addText("A supervisor has a few moments on the floor to answer. The right answer is somewhere in 2,300 pages.", { ...H, x: 0.5, y: 0.8, w: 9, h: 1.1, fontSize: 24 });
  const stats = [["2,320", "pages of procedures and manuals, checked on every question"], ["seconds", "to get an answer with the document and page next to it"], ["0", "guesses. If it is not in the documents, it says so"]];
  stats.forEach(([n, l], i) => {
    const x = 0.5 + i * 3.05;
    s.addShape(pres.ShapeType.roundRect, { x, y: 2.15, w: 2.9, h: 1.7, fill: { color: PANEL }, line: { color: PANEL }, rectRadius: 0.08 });
    s.addText(n, { ...H, x: x + 0.2, y: 2.25, w: 2.5, h: 0.85, fontSize: 40, color: PURPLE });
    s.addText(l, { ...B, x: x + 0.2, y: 3.1, w: 2.5, h: 0.7, fontSize: 12, color: MUTE });
  });
  s.addText("Today the choice is to look it up by hand and lose the moment, or answer from memory and hope it is right. We built a system that reads all 2,300 pages for every question and hands back a factual answer, with the page, in seconds.", { ...B, x: 0.5, y: 4.15, w: 9, h: 1.1, fontSize: 15 });
  s.addNotes("The hook: every question is checked against all 2,320 pages, and the answer shows the page it came from.");
}

// 3. What we built
{
  const s = pres.addSlide();
  s.background = { color: "FFFFFF" };
  s.addText("What we built", { ...B, x: 0.5, y: 0.4, w: 9, h: 0.35, fontSize: 14, color: MUTE });
  s.addText("Ask in plain words. Get the page.", { ...H, x: 0.5, y: 0.75, w: 9, h: 0.6, fontSize: 26 });
  const steps = [
    [PURPLE, "1. The supervisor types the question", "In a chat window, in their own words."],
    [BLUE, "2. Our agents search 2,300+ pages", "Procedures and manuals across safety, maintenance and quality, all at once."],
    [GREEN, "3. Only the best matches come back", "The answer shows just the parts that fit the question, each with its document and page. Click the page to see it."],
    [AMBER, "4. No answer? Then, and only then, a manager", "The one time a person steps in. Their answer is saved, so the next person gets it right away."],
  ];
  steps.forEach(([c, h, b], i) => {
    const x = 0.5 + i * 2.3;
    s.addShape(pres.ShapeType.roundRect, { x, y: 1.55, w: 2.1, h: 2.05, fill: { color: PANEL }, line: { color: PANEL }, rectRadius: 0.08 });
    s.addShape(pres.ShapeType.ellipse, { x: x + 0.15, y: 1.7, w: 0.3, h: 0.3, fill: { color: c }, line: { color: c } });
    s.addText(h, { ...H, x: x + 0.15, y: 2.08, w: 1.8, h: 0.55, fontSize: 12.5 });
    s.addText(b, { ...B, x: x + 0.15, y: 2.65, w: 1.8, h: 0.9, fontSize: 10.5, color: MUTE });
    if (i < 3) s.addText("›", { ...H, x: x + 2.1, y: 2.3, w: 0.2, h: 0.5, fontSize: 28, color: MUTE, align: "center" });
  });
  s.addImage({ path: "shots/chat_crop.png", x: 0.5, y: 3.8, w: 3.4, h: 1.72 });
  s.addText("The supervisor's screen: the answer, then the quote with a link to page 15 of the OSHA lockout booklet.", { ...B, x: 4.1, y: 3.85, w: 5.4, h: 0.5, fontSize: 11, color: MUTE });
  s.addText("Time saved on every question, and a manager's time spent only when the documents run out. Time is money.", { ...H, x: 4.1, y: 4.5, w: 5.4, h: 0.9, fontSize: 15 });
  s.addNotes("Four steps. The manager is step four and only step four.");
}

pres.writeFile({ fileName: "Manufacturing_RAG_deck.pptx" }).then((f) => console.log("wrote", f));
