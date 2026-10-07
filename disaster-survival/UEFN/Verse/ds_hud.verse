# Disaster Survival (UEFN) - HUD per player: timer, missions, secret mission, event banner,
# status line and the recap / match story panel.

using { /Fortnite.com/UI }
using { /Verse.org/Simulation }
using { /Verse.org/Colors }
using { /UnrealEngine.com/Temporary/UI }
using { /UnrealEngine.com/Temporary/SpatialMath }

DsMsg<localizes>(S:string):message = "{S}"

DsGold : color = color{R := 1.0, G := 0.78, B := 0.25}
DsWhite : color = color{R := 1.0, G := 0.98, B := 0.94}
DsMuted : color = color{R := 0.70, G := 0.72, B := 0.76}
DsGreen : color = color{R := 0.50, G := 0.85, B := 0.56}
DsRed : color = color{R := 1.0, G := 0.55, B := 0.48}
DsPurple : color = color{R := 0.80, G := 0.66, B := 1.0}
DsPanel : color = color{R := 0.02, G := 0.025, B := 0.035}

ds_hud := class:
    PlayerRef : player

    TopText : text_block = text_block{DefaultTextColor := DsWhite}
    SubText : text_block = text_block{DefaultTextColor := DsGold}
    MissionText : text_block = text_block{DefaultTextColor := DsWhite}
    SecretText : text_block = text_block{DefaultTextColor := DsPurple}
    BannerText : text_block = text_block{DefaultTextColor := DsWhite}
    StatusText : text_block = text_block{DefaultTextColor := DsRed}
    PanelTitle : text_block = text_block{DefaultTextColor := DsGold}
    PanelText : text_block = text_block{DefaultTextColor := DsWhite}

    var MaybeCanvas : ?canvas = false
    var MaybeMissionBox : ?overlay = false
    var MaybeBannerBox : ?overlay = false
    var MaybePanel : ?overlay = false
    var Banners : []string = array{}
    var Active : logic = false

    Show():void =
        if (UI := GetPlayerUI[PlayerRef], not Active?):
            C := Build()
            UI.AddWidget(C)
            set MaybeCanvas = option{C}
            set Active = true
            spawn{ BannerLoop() }

    Hide():void =
        set Active = false
        if (UI := GetPlayerUI[PlayerRef], C := MaybeCanvas?):
            UI.RemoveWidget(C)
        set MaybeCanvas = false

    Banner(Text:string):void =
        if (Banners.Length >= 4):
            var Rest : []string = array{}
            for (I -> S : Banners, I > 0):
                set Rest += array{S}
            set Banners = Rest
        set Banners += array{Text}

    BannerLoop()<suspends>:void =
        loop:
            if (not Active?):
                break
            if (First := Banners[0]):
                var Rest : []string = array{}
                for (I -> S : Banners, I > 0):
                    set Rest += array{S}
                set Banners = Rest
                BannerText.SetText(DsMsg(First))
                if (Box := MaybeBannerBox?) then Box.SetVisibility(widget_visibility.Visible)
                Sleep(3.5)
            else:
                if (Box := MaybeBannerBox?) then Box.SetVisibility(widget_visibility.Collapsed)
                Sleep(0.25)

    # Playing: missions visible, panel hidden. Recap: panel visible.
    ShowPlaying(Top:string, Sub:string, Missions:string, Secret:string, Status:string):void =
        TopText.SetText(DsMsg(Top))
        SubText.SetText(DsMsg(Sub))
        MissionText.SetText(DsMsg(Missions))
        SecretText.SetText(DsMsg(Secret))
        StatusText.SetText(DsMsg(Status))
        if (Box := MaybeMissionBox?) then Box.SetVisibility(widget_visibility.Visible)
        if (P := MaybePanel?) then P.SetVisibility(widget_visibility.Collapsed)

    ShowCenter(Top:string, Sub:string, Status:string):void =
        TopText.SetText(DsMsg(Top))
        SubText.SetText(DsMsg(Sub))
        StatusText.SetText(DsMsg(Status))
        if (Box := MaybeMissionBox?) then Box.SetVisibility(widget_visibility.Collapsed)
        if (P := MaybePanel?) then P.SetVisibility(widget_visibility.Collapsed)

    ShowPanel(Top:string, Title:string, Body:string):void =
        TopText.SetText(DsMsg(Top))
        SubText.SetText(DsMsg(""))
        StatusText.SetText(DsMsg(""))
        PanelTitle.SetText(DsMsg(Title))
        PanelText.SetText(DsMsg(Body))
        if (Box := MaybeMissionBox?) then Box.SetVisibility(widget_visibility.Collapsed)
        if (P := MaybePanel?) then P.SetVisibility(widget_visibility.Visible)

    Backed(Inner:widget, Pad:float):overlay =
        overlay:
            Slots := array:
                overlay_slot:
                    Widget := color_block{DefaultColor := DsPanel, DefaultOpacity := 0.75}
                    HorizontalAlignment := horizontal_alignment.Fill
                    VerticalAlignment := vertical_alignment.Fill
                overlay_slot:
                    Widget := Inner
                    Padding := margin{Left := Pad, Top := Pad * 0.7, Right := Pad, Bottom := Pad * 0.7}

    Build():canvas =
        TopBox := Backed(stack_box{Orientation := orientation.Vertical, Slots := array{
            stack_box_slot{Widget := TopText, HorizontalAlignment := horizontal_alignment.Center},
            stack_box_slot{Widget := SubText, HorizontalAlignment := horizontal_alignment.Center}}}, 22.0)

        MissionBox := Backed(stack_box{Orientation := orientation.Vertical, Slots := array{
            stack_box_slot{Widget := text_block{DefaultText := DsMsg("MISSIONS"), DefaultTextColor := DsGold}},
            stack_box_slot{Widget := MissionText, Padding := margin{Top := 6.0}},
            stack_box_slot{Widget := text_block{DefaultText := DsMsg("SECRET MISSION  (only you can see this)"), DefaultTextColor := DsGold}, Padding := margin{Top := 14.0}},
            stack_box_slot{Widget := SecretText, Padding := margin{Top := 4.0}}}}, 20.0)
        set MaybeMissionBox = option{MissionBox}

        BannerBox := Backed(BannerText, 24.0)
        BannerBox.SetVisibility(widget_visibility.Collapsed)
        set MaybeBannerBox = option{BannerBox}

        Panel := Backed(stack_box{Orientation := orientation.Vertical, Slots := array{
            stack_box_slot{Widget := PanelTitle},
            stack_box_slot{Widget := PanelText, Padding := margin{Top := 12.0}}}}, 34.0)
        Panel.SetVisibility(widget_visibility.Collapsed)
        set MaybePanel = option{Panel}

        canvas:
            Slots := array:
                canvas_slot:
                    Anchors := anchors{Minimum := vector2{X := 0.5, Y := 0.0}, Maximum := vector2{X := 0.5, Y := 0.0}}
                    Alignment := vector2{X := 0.5, Y := 0.0}
                    Offsets := margin{Left := 0.0, Top := 20.0, Right := 0.0, Bottom := 0.0}
                    SizeToContent := true
                    Widget := TopBox
                canvas_slot:
                    Anchors := anchors{Minimum := vector2{X := 0.0, Y := 0.3}, Maximum := vector2{X := 0.0, Y := 0.3}}
                    Alignment := vector2{X := 0.0, Y := 0.0}
                    Offsets := margin{Left := 24.0, Top := 0.0, Right := 0.0, Bottom := 0.0}
                    SizeToContent := true
                    Widget := MissionBox
                canvas_slot:
                    Anchors := anchors{Minimum := vector2{X := 0.5, Y := 0.0}, Maximum := vector2{X := 0.5, Y := 0.0}}
                    Alignment := vector2{X := 0.5, Y := 0.0}
                    Offsets := margin{Left := 0.0, Top := 140.0, Right := 0.0, Bottom := 0.0}
                    SizeToContent := true
                    ZOrder := 5
                    Widget := BannerBox
                canvas_slot:
                    Anchors := anchors{Minimum := vector2{X := 0.5, Y := 1.0}, Maximum := vector2{X := 0.5, Y := 1.0}}
                    Alignment := vector2{X := 0.5, Y := 1.0}
                    Offsets := margin{Left := 0.0, Top := -150.0, Right := 0.0, Bottom := 0.0}
                    SizeToContent := true
                    Widget := StatusText
                canvas_slot:
                    Anchors := anchors{Minimum := vector2{X := 0.5, Y := 0.5}, Maximum := vector2{X := 0.5, Y := 0.5}}
                    Alignment := vector2{X := 0.5, Y := 0.5}
                    Offsets := margin{Left := 0.0, Top := 30.0, Right := 0.0, Bottom := 0.0}
                    SizeToContent := true
                    ZOrder := 10
                    Widget := Panel
