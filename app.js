// Paste your Formspree endpoint URL here to collect coworker feedback.
// Sign up free at https://formspree.io (50 submits/month, no backend needed).
// Leave empty during local testing — submissions log to console instead.
const FEEDBACK_ENDPOINT = "";

const $ = (id) => document.getElementById(id);

const PAGE_SIZE = 10;

const fmt = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

const state = { techs: [], cat: "all", page: 1 };

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
  const reddit = data.reddit || { subreddits: [], total_posts_scanned: 0 };
  const github = data.github || { queries: [], total_repos_scanned: 0 };

  $("meta").textContent =
    `Snapshot ${fmt.format(generated)} · ` +
    `Reddit: ${reddit.total_posts_scanned} posts / ${reddit.subreddits.length} subs · ` +
    `GitHub: ${github.total_repos_scanned} repos / ${github.queries.length} queries`;

  $("subs").textContent =
    reddit.subreddits.map((s) => `r/${s.name}`).join(", ");

  renderSummary(data, reddit, github);
  renderFilters(data.technologies);
  renderList();
  renderTopStarred(github.top_starred || []);
  initFeedback();
}

function renderSummary(data, reddit, github) {
  const techs = data.technologies;
  if (!techs.length) return;
  const section = $("summary");
  section.hidden = false;

  const top3 = techs.slice(0, 3).map((t) => t.name);
  const totalMentions = techs.reduce((a, t) => a + t.count, 0);
  const ledeBits = [
    `Across <strong>${reddit.subreddits.length}</strong> Reddit communities`,
    `and <strong>${github.queries.length}</strong> GitHub queries we found`,
    `<strong>${techs.length}</strong> technologies mentioned <strong>${totalMentions}</strong> times`,
    `(<strong>${reddit.total_posts_scanned}</strong> posts + <strong>${github.total_repos_scanned}</strong> repos).`,
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
    .filter((t) => (t.reddit_count || 0) > 0 && (t.github_count || 0) > 0)
    .sort((a, b) => b.count - a.count)
    .slice(0, 5);

  if (reach.length === 0) {
    const li = document.createElement("li");
    li.innerHTML = `<span class="subs">No tech showed up on both Reddit and GitHub yet.</span>`;
    reachList.appendChild(li);
  } else {
    for (const r of reach) {
      const li = document.createElement("li");
      li.innerHTML = `<span class="name"></span><span class="subs"></span>`;
      li.querySelector(".name").textContent = r.name;
      li.querySelector(".subs").textContent = `r:${r.reddit_count} · g:${r.github_count}`;
      reachList.appendChild(li);
    }
  }
}

function renderTopStarred(repos) {
  if (!repos || !repos.length) return;
  const sidebar = $("sidebar");
  sidebar.hidden = false;
  const list = $("top-starred");
  list.innerHTML = "";
  repos.forEach((repo, i) => {
    const li = document.createElement("li");
    const rank = document.createElement("span");
    rank.className = "ts-rank";
    rank.textContent = `#${i + 1}`;

    const body = document.createElement("div");
    const name = document.createElement("div");
    name.className = "ts-name";
    const a = document.createElement("a");
    a.href = repo.url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.textContent = repo.name;
    name.appendChild(a);

    const meta = document.createElement("span");
    meta.className = "ts-meta";
    const lang = repo.language ? ` · ${repo.language}` : "";
    meta.textContent = `★${repo.stars.toLocaleString()}${lang}`;

    body.append(name, meta);
    li.append(rank, body);
    list.appendChild(li);
  });
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
    state.cat = e.target.dataset.cat;
    state.page = 1;
    renderList();
  });
  state.techs = techs;

  $("prev-page").addEventListener("click", () => { if (state.page > 1) { state.page--; renderList(); } });
  $("next-page").addEventListener("click", () => { state.page++; renderList(); });
}

function renderList() {
  const list = $("leaderboard");
  list.innerHTML = "";
  const filtered = state.cat === "all" ? state.techs : state.techs.filter((t) => t.category === state.cat);
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  if (state.page > totalPages) state.page = totalPages;

  const startIdx = (state.page - 1) * PAGE_SIZE;
  const slice = filtered.slice(startIdx, startIdx + PAGE_SIZE);
  slice.forEach((t, i) => list.appendChild(rowFor(t, startIdx + i + 1)));

  const pag = $("pagination");
  pag.hidden = filtered.length <= PAGE_SIZE;
  $("page-info").textContent =
    `Page ${state.page} of ${totalPages} · ${filtered.length} ${filtered.length === 1 ? "tech" : "techs"}`;
  $("prev-page").disabled = state.page <= 1;
  $("next-page").disabled = state.page >= totalPages;
}

function rowFor(t, rank) {
  const li = document.createElement("li");
  const d = document.createElement("details");
  d.className = "row";

  const r = t.reddit_count || 0;
  const g = t.github_count || 0;
  const sum = document.createElement("summary");
  sum.innerHTML = `
    <span class="rank">#${rank}</span>
    <span><span class="name"></span><span class="cat"></span></span>
    <span class="count">
      <span class="total"></span>
      <span class="split"><em></em>r · <em></em>g</span>
    </span>
  `;
  sum.querySelector(".name").textContent = t.name;
  sum.querySelector(".cat").textContent = t.category;
  sum.querySelector(".total").textContent = t.count;
  const ems = sum.querySelectorAll(".split em");
  ems[0].textContent = r;
  ems[1].textContent = g;
  d.appendChild(sum);

  const drill = document.createElement("div");
  drill.className = "drilldown";

  if ((t.posts || []).length) {
    const block = document.createElement("div");
    block.className = "drilldown-block";
    block.innerHTML = `<h4>From Reddit</h4>`;
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
    block.appendChild(ul);
    drill.appendChild(block);
  }

  if ((t.repos || []).length) {
    const block = document.createElement("div");
    block.className = "drilldown-block";
    block.innerHTML = `<h4>From GitHub</h4>`;
    const ul = document.createElement("ul");
    ul.className = "repos";
    for (const repo of t.repos) {
      const item = document.createElement("li");
      const a = document.createElement("a");
      a.href = repo.url;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.textContent = repo.name;
      const meta = document.createElement("span");
      meta.className = "repo-meta";
      const lang = repo.language ? ` · ${repo.language}` : "";
      meta.textContent = ` · ★${repo.stars.toLocaleString()}${lang}`;
      item.append(a, meta);
      if (repo.description) {
        const desc = document.createElement("div");
        desc.className = "repo-desc";
        desc.textContent = repo.description;
        item.append(desc);
      }
      ul.appendChild(item);
    }
    block.appendChild(ul);
    drill.appendChild(block);
  }

  d.appendChild(drill);
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
