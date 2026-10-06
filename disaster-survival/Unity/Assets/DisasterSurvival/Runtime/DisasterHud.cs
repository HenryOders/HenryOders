using System.Collections.Generic;
using System.Linq;
using DisasterSurvival.Core;
using UnityEngine;
using UnityEngine.UI;

namespace DisasterSurvival
{
    /// <summary>
    /// Complete HUD built in code (no prefab needed): timer, missions, secret mission, event banner,
    /// interaction prompt, round recap with rank progress and the match story at the end.
    /// Replace it with your own UI later; everything it shows comes from DisasterGameManager.
    /// </summary>
    public class DisasterHud : MonoBehaviour
    {
        public Color accent = new Color(1f, 0.78f, 0.25f);
        public float bannerSeconds = 3.5f;

        Text _top, _missions, _banner, _prompt, _center, _panelText;
        GameObject _panel;
        readonly Queue<string> _bannerQueue = new Queue<string>();
        float _bannerTime;
        Font _font;

        void OnEnable()
        {
            DisasterGameManager.Announcement += QueueBanner;
            DisasterGameManager.MissionCompleted += OnMission;
        }

        void OnDisable()
        {
            DisasterGameManager.Announcement -= QueueBanner;
            DisasterGameManager.MissionCompleted -= OnMission;
        }

        void Awake() { Build(); }

        void QueueBanner(string text)
        {
            if (_bannerQueue.Count > 4) _bannerQueue.Dequeue();
            _bannerQueue.Enqueue(text);
        }

        void OnMission(PlayerAgent p, MissionDef m)
        {
            if (p != null && p.isLocalPlayer && m.Kind != MissionKind.Survive && m.Kind != MissionKind.LastSurvivor)
                QueueBanner($"<color=#{Hex(accent)}>Mission complete:</color> {m.Title}  +{m.Reward} SP");
        }

        // ------------------------------------------------------------ build

        void Build()
        {
            // Unity 2022.2+ ships "LegacyRuntime.ttf", older versions "Arial.ttf"
            try { _font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf"); } catch { _font = null; }
            if (_font == null) { try { _font = Resources.GetBuiltinResource<Font>("Arial.ttf"); } catch { _font = null; } }

            var canvasGo = new GameObject("DisasterHUD", typeof(Canvas), typeof(CanvasScaler));
            canvasGo.transform.SetParent(transform, false);
            var canvas = canvasGo.GetComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            canvas.sortingOrder = 50;
            var scaler = canvasGo.GetComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(1920, 1080);
            scaler.matchWidthOrHeight = 0.5f;

            _top = MakeText(canvasGo.transform, "Top", new Vector2(0.5f, 1f), new Vector2(0f, -28f), new Vector2(900, 90), 34, TextAnchor.UpperCenter);
            _missions = MakeText(canvasGo.transform, "Missions", new Vector2(0f, 1f), new Vector2(28f, -28f), new Vector2(560, 520), 22, TextAnchor.UpperLeft, true);
            _banner = MakeText(canvasGo.transform, "Banner", new Vector2(0.5f, 1f), new Vector2(0f, -150f), new Vector2(1300, 120), 30, TextAnchor.UpperCenter);
            _prompt = MakeText(canvasGo.transform, "Prompt", new Vector2(0.5f, 0f), new Vector2(0f, 110f), new Vector2(1000, 60), 26, TextAnchor.LowerCenter);
            _center = MakeText(canvasGo.transform, "Center", new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(1200, 200), 56, TextAnchor.MiddleCenter);

            _panel = new GameObject("RecapPanel", typeof(RectTransform), typeof(Image));
            _panel.transform.SetParent(canvasGo.transform, false);
            var rt = (RectTransform)_panel.transform;
            rt.anchorMin = rt.anchorMax = new Vector2(0.5f, 0.5f);
            rt.sizeDelta = new Vector2(1100, 760);
            _panel.GetComponent<Image>().color = new Color(0.04f, 0.045f, 0.06f, 0.92f);
            _panelText = MakeText(_panel.transform, "RecapText", new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(1020, 700), 24, TextAnchor.UpperLeft, false);
            _panel.SetActive(false);
        }

        Text MakeText(Transform parent, string name, Vector2 anchor, Vector2 pos, Vector2 size, int fontSize, TextAnchor align, bool panel = false)
        {
            Transform holder = parent;
            if (panel)
            {
                var bg = new GameObject(name + "Bg", typeof(RectTransform), typeof(Image));
                bg.transform.SetParent(parent, false);
                var brt = (RectTransform)bg.transform;
                brt.anchorMin = brt.anchorMax = brt.pivot = anchor;
                brt.anchoredPosition = pos;
                brt.sizeDelta = size;
                bg.GetComponent<Image>().color = new Color(0.03f, 0.035f, 0.05f, 0.62f);
                holder = bg.transform;
                pos = Vector2.zero;
                anchor = new Vector2(0.5f, 0.5f);
                size -= new Vector2(36, 32);
            }
            var go = new GameObject(name, typeof(RectTransform), typeof(Text), typeof(Outline));
            go.transform.SetParent(holder, false);
            var t = go.GetComponent<Text>();
            t.font = _font;
            t.fontSize = fontSize;
            t.alignment = align;
            t.supportRichText = true;
            t.horizontalOverflow = HorizontalWrapMode.Wrap;
            t.verticalOverflow = VerticalWrapMode.Overflow;
            t.color = Color.white;
            go.GetComponent<Outline>().effectColor = new Color(0f, 0f, 0f, 0.6f);
            var r = (RectTransform)go.transform;
            r.anchorMin = r.anchorMax = r.pivot = anchor;
            r.anchoredPosition = pos;
            r.sizeDelta = size;
            return t;
        }

        // ------------------------------------------------------------ update

        void Update()
        {
            var gm = DisasterGameManager.Instance;
            if (gm == null || _top == null) return;
            UpdateBanner();

            var local = gm.LocalPlayer;
            var round = gm.Round;
            _missions.transform.parent.gameObject.SetActive(gm.CurrentStage == DisasterGameManager.Stage.Playing);
            _panel.SetActive(gm.CurrentStage == DisasterGameManager.Stage.Recap || gm.CurrentStage == DisasterGameManager.Stage.MatchOver);
            _center.text = "";
            _prompt.text = "";

            switch (gm.CurrentStage)
            {
                case DisasterGameManager.Stage.Countdown:
                    int n = gm.Session.History.Count + 1;
                    _top.text = $"ROUND {n} OF {gm.Session.RoundsTotal}";
                    _center.text = $"Next disaster in {Mathf.CeilToInt(gm.StageTimeLeft)}";
                    break;

                case DisasterGameManager.Stage.Playing:
                    var t = Mathf.CeilToInt(round.TimeLeft);
                    _top.text = $"<b>{round.Disaster.Name.ToUpperInvariant()}</b>   {t / 60}:{t % 60:00}\n<size=20><color=#{Hex(accent)}>{PhaseText(round.Phase)}</color>{ActiveEventsText(round)}</size>";
                    _missions.text = MissionText(round, gm.StateOf(local));
                    _prompt.text = PromptText(local);
                    break;

                case DisasterGameManager.Stage.Recap:
                    _top.text = "ROUND OVER";
                    _panelText.text = RecapText(gm, local);
                    break;

                case DisasterGameManager.Stage.MatchOver:
                    _top.text = "MATCH OVER";
                    _panelText.text = MatchOverText(gm);
                    if (DSInput.InteractPressed()) gm.StartMatch();
                    break;
            }
        }

        void UpdateBanner()
        {
            _bannerTime -= Time.deltaTime;
            if (_bannerTime <= 0f)
            {
                _banner.text = _bannerQueue.Count > 0 ? _bannerQueue.Dequeue() : "";
                _bannerTime = _banner.text.Length > 0 ? bannerSeconds : 0f;
            }
        }

        static string PhaseText(ArcPhase p) =>
            p == ArcPhase.Opening ? "IT BEGINS" : p == ArcPhase.Midgame ? "GETTING WORSE" : "FINAL STAGE";

        static string ActiveEventsText(RoundController r)
        {
            if (r.ActiveEvents.Count == 0) return "";
            return "   |   " + string.Join("   |   ", r.ActiveEvents.Select(e => $"{e.Def.Title} {Mathf.CeilToInt(e.EndsAt - r.Elapsed)}s"));
        }

        string MissionText(RoundController round, PlayerState me)
        {
            if (me == null) return "";
            var lines = new List<string> { "<b>MISSIONS</b>" };
            foreach (var m in round.Missions)
            {
                bool done = me.Completed.Contains(m.Id);
                string progress = "";
                if (!done && m.Kind == MissionKind.ActivateObjects)
                    progress = $"  ({(me.Activations.TryGetValue(m.TargetId, out var a) ? a : 0)}/{m.Target})";
                if (!done && m.Kind == MissionKind.HoldZone)
                    progress = $"  ({Mathf.FloorToInt(me.ZoneSeconds.TryGetValue(m.TargetId, out var s) ? s : 0f)}/{m.Target}s)";
                lines.Add(done
                    ? $"<color=#7fd88f>DONE  {m.Title}  +{m.Reward}</color>"
                    : $"<color=#{Hex(accent)}>+{m.Reward}</color>  {m.Title}{progress}");
            }
            if (me.Secret != null)
            {
                lines.Add("");
                lines.Add($"<b>SECRET</b>  <color=#c9a7ff>{me.Secret.Text}</color>  <color=#{Hex(accent)}>+{ContentLibrary.SecretReward}</color>");
                lines.Add("<size=16><color=#9aa0aa>Nobody else can see this.</color></size>");
            }
            lines.Add("");
            lines.Add($"<b>{me.Sp} SP</b> this round");
            return string.Join("\n", lines);
        }

        static string PromptText(PlayerAgent local)
        {
            if (local == null) return "";
            if (!local.Alive) return "<color=#ff8a7a>You are out.</color> Watch the others until the round ends.";
            if (local.Injured) return local.CarriedBy != null
                ? $"<color=#7fd88f>{local.CarriedBy.displayName} is carrying you to safety.</color>"
                : "<color=#ff8a7a>You are injured.</color> Someone has to carry you to the rescue station.";
            if (local.CarriedPlayer != null) return $"Carry {local.CarriedPlayer.displayName} to the rescue station   [G] put down";
            if (local.CarriedItem != null) return "Bring it to the rescue station   [G] drop";
            var i = local.FindInteractable();
            return i != null ? $"[E] {i.Prompt(local)}" : "";
        }

        string RecapText(DisasterGameManager gm, PlayerAgent local)
        {
            var lines = new List<string>();
            foreach (var l in gm.LastRecap) lines.Add(lines.Count == 0 ? $"<size=34><b>{l}</b></size>" : l);
            if (local != null && gm.LastProgress.TryGetValue(local.playerId, out var up))
            {
                lines.Add("");
                lines.Add($"<color=#{Hex(accent)}><b>+{up.SpGained} SP</b></color>   Rank: <b>{up.NewRank}</b>" + (up.RankUp ? $"   <color=#7fd88f>RANK UP!</color>" : ""));
                foreach (var u in up.NewUnlocks) lines.Add($"<color=#c9a7ff>Unlocked: {u.Name}</color>");
                if (up.NextRankMissing.Count > 0) lines.Add($"<size=20><color=#9aa0aa>{string.Join("  |  ", up.NextRankMissing)}</color></size>");
            }
            lines.Add("");
            lines.Add($"<size=20><color=#9aa0aa>Next round in {Mathf.CeilToInt(gm.StageTimeLeft)}</color></size>");
            return string.Join("\n", lines);
        }

        string MatchOverText(DisasterGameManager gm)
        {
            var lines = new List<string> { "<size=34><b>The story of this match</b></size>" };
            lines.AddRange(gm.Session.MatchStory());
            lines.Add("");
            lines.Add("<b>Leaderboard</b>");
            int place = 1;
            foreach (var kv in gm.Session.Leaderboard()) lines.Add($"{place++}.  {gm.Session.NameOf(kv.Key)}   <color=#{Hex(accent)}>{kv.Value} SP</color>");
            lines.Add("");
            lines.Add("<size=22>[E] Play again</size>");
            return string.Join("\n", lines);
        }

        static string Hex(Color c) => ColorUtility.ToHtmlStringRGB(c);
    }
}
