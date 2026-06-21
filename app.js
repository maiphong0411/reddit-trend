// Paste your Formspree endpoint URL here to collect coworker feedback.
// Sign up free at https://formspree.io (50 submits/month, no backend needed).
// Leave empty during local testing — submissions log to console instead.
const FEEDBACK_ENDPOINT = "";

const $ = (id) => document.getElementById(id);

const fmt = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

async function load() {
  let data;
  try {
    const r = await fetch("./data/latest.json", { cache: "no-store" });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    data = await r.json();
  } catch (e) {
    $("meta").textContent = "Could not load data/latest.json.";
    $("empty").hidden = false;
    initFeedback();
    return;
  }

  if (!data.technologies || data.technologies.length === 0) {
    $("empty").hidden = false;
    $("meta").textContent = "No mentions found in this snapshot.";
    initFeedback();
    return;
  }

  const generated = new Date(data.generated_at);
  $("meta").textContent =
    `Snapshot ${fmt.format(generated)} · ${data.total_posts_scanned} posts across ${data.subreddits.length} subs`;
  $("subs").textContent = data.subreddits.map((s) => `r/${s.name}`).join(", ");

  renderSummary(data);
  renderFilters(data.technologies);
  renderList(data.technologies, "all");
  initFeedback();
}

function renderSummary(data) {
  const techs = data.technologies;
  if (!techs.length) return;
  const section = $("summary");
  section.hidden = false;

  const top3 = techs.slice(0, 3).map((t) => t.name);
  const totalMentions = techs.reduce((a, t) => a + t.count, 0);
  const ledeBits = [
    `Across <strong>${data.subreddits.length}</strong> communities`,
    `we picked up <strong>${techs.length}</strong> distinct technologies`,
    `mentioned <strong>${totalMentions}</strong> times in <strong>${data.total_posts_scanned}</strong> hot posts.`,
  ];
  if (top3.length === 3) {
    ledeBits.push(`Loudest right now: <strong>${top3[0]}</strong>, <strong>${top3[1]}</strong>, <strong>${top3[2]}</strong>.`);
  }
  $("summary-lede").innerHTML = ledeBits.join(" ");

  const topList = $("summary-top");
  topList.innerHTML = "";
  techs.slice(0, 5).forEach((t, i) => {
    const li = document.createElement("li");
    li.innerHTML = `<span class="pos">#${i + 1}</span><span class="name"></span><span class="n"></span>`;
    li.querySelector(".name").textContent = t.name;
    li.querySelector(".n").textContent = t.count;
    topList.appendChild(li);
  });

  const byCat = new Map();
  for (const t of techs) {
    const prev = byCat.get(t.category);
    if (!prev || t.count > prev.count) byCat.set(t.category, t);
  }
  const catList = $("summary-cat");
  catList.innerHTML = "";
  [...byCat.entries()]
    .sort((a, b) => b[1].count - a[1].count)
    .forEach(([cat, leader]) => {
      const li = document.createElement("li");
      li.innerHTML = `<span class="cat-key"></span><span class="cat-leader"></span>`;
      li.querySelector(".cat-key").textContent = cat;
      li.querySelector(".cat-leader").textContent = `${leader.name} · ${leader.count}`;
      catList.appendChild(li);
    });

  const reachList = $("summary-reach");
  reachList.innerHTML = "";
  const reach = techs
    .map((t) => ({ name: t.name, subs: new Set(t.posts.map((p) => p.subreddit)).size, count: t.count }))
    .filter((t) => t.subs >= 2)
    .sort((a, b) => b.subs - a.subs || b.count - a.count)
    .slice(0, 5);

  if (reach.length === 0) {
    const li = document.createElement("li");
    li.innerHTML = `<span class="subs">No tech appeared in more than one sub yet.</span>`;
    reachList.appendChild(li);
  } else {
    for (const r of reach) {
      const li = document.createElement("li");
      li.innerHTML = `<span class="name"></span><span class="subs"></span>`;
      li.querySelector(".name").textContent = r.name;
      li.querySelector(".subs").textContent = `${r.subs} subs · ${r.count} mentions`;
      reachList.appendChild(li);
    }
  }
}

function renderFilters(techs) {
  const cats = [...new Set(techs.map((t) => t.category))].sort();
  const nav = $("filters");
  nav.hidden = false;
  for (const cat of cats) {
    const b = document.createElement("button");
    b.dataset.cat = cat;
    b.textContent = cat;
    nav.appendChild(b);
  }
  nav.addEventListener("click", (e) => {
    if (e.target.tagName !== "BUTTON") return;
    for (const b of nav.querySelectorAll("button")) b.classList.toggle("active", b === e.target);
    renderList(window.__techs, e.target.dataset.cat);
  });
  window.__techs = techs;
}

function renderList(techs, cat) {
  const list = $("leaderboard");
  list.innerHTML = "";
  const filtered = cat === "all" ? techs : techs.filter((t) => t.category === cat);
  filtered.forEach((t, i) => list.appendChild(rowFor(t, i + 1)));
}

function rowFor(t, rank) {
  const li = document.createElement("li");
  const d = document.createElement("details");
  d.className = "row";

  const sum = document.createElement("summary");
  sum.innerHTML = `
    <span class="rank">#${rank}</span>
    <span><span class="name"></span><span class="cat"></span></span>
    <span class="count"><span class="n"></span><small>posts</small></span>
  `;
  sum.querySelector(".name").textContent = t.name;
  sum.querySelector(".cat").textContent = t.category;
  sum.querySelector(".n").textContent = t.count;
  d.appendChild(sum);

  const ul = document.createElement("ul");
  ul.className = "posts";
  for (const p of t.posts) {
    const item = document.createElement("li");
    const a = document.createElement("a");
    a.href = p.permalink;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.textContent = p.title;
    const meta = document.createElement("span");
    meta.className = "post-meta";
    meta.textContent = ` · r/${p.subreddit}`;
    item.append(a, meta);
    ul.appendChild(item);
  }
  d.appendChild(ul);
  li.appendChild(d);
  return li;
}

function initFeedback() {
  const submitBtn = $("feedback-submit");
  const status = $("feedback-status");
  const comment = $("feedback-comment");
  const voteBtns = document.querySelectorAll(".vote");
  let chosenVote = null;

  const refreshEnabled = () => {
    submitBtn.disabled = !chosenVote && comment.value.trim().length === 0;
  };

  voteBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      chosenVote = chosenVote === btn.dataset.vote ? null : btn.dataset.vote;
      voteBtns.forEach((b) => {
        const on = b.dataset.vote === chosenVote;
        b.classList.toggle("selected", on);
        b.setAttribute("aria-checked", on ? "true" : "false");
      });
      refreshEnabled();
    });
  });

  comment.addEventListener("input", refreshEnabled);

  submitBtn.addEventListener("click", async () => {
    submitBtn.disabled = true;
    status.className = "feedback-status";
    status.textContent = "Sending…";

    const payload = {
      vote: chosenVote,
      comment: comment.value.trim() || null,
      page: location.pathname,
      sent_at: new Date().toISOString(),
      user_agent: navigator.userAgent,
    };

    try {
      if (FEEDBACK_ENDPOINT) {
        const r = await fetch(FEEDBACK_ENDPOINT, {
          method: "POST",
          headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify(payload),
        });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
      } else {
        console.log("[feedback demo mode — no endpoint configured]", payload);
        await new Promise((res) => setTimeout(res, 350));
      }
      status.className = "feedback-status ok";
      status.textContent = FEEDBACK_ENDPOINT ? "Thanks — sent." : "Demo mode: see browser console.";
      comment.value = "";
      chosenVote = null;
      voteBtns.forEach((b) => {
        b.classList.remove("selected");
        b.setAttribute("aria-checked", "false");
      });
    } catch (e) {
      status.className = "feedback-status err";
      status.textContent = "Couldn't send. Try again.";
      submitBtn.disabled = false;
    }
  });

  refreshEnabled();
}

load();
