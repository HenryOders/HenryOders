# Mansion Tycoon - HUD (immer sichtbar) und Estate-Tablet (Menue mit 7 Reitern).

using { /Fortnite.com/UI }
using { /Verse.org/Simulation }
using { /Verse.org/Colors }
using { /UnrealEngine.com/Temporary/UI }
using { /UnrealEngine.com/Temporary/SpatialMath }

S2M<localizes>(S:string):message = "{S}"

GoldColor : color = color{R := 0.95, G := 0.74, B := 0.30}
PanelColor : color = color{R := 0.02, G := 0.02, B := 0.03}
RowColor : color = color{R := 0.09, G := 0.08, B := 0.07}
TextColor : color = color{R := 1.0, G := 0.97, B := 0.92}
MutedColor : color = color{R := 0.66, G := 0.61, B := 0.54}
BarBackColor : color = color{R := 0.18, G := 0.15, B := 0.11}

TabNames : []string = array{"MANSION", "BUILD", "FURNITURE", "GARAGE", "STAFF", "UPGRADES", "QUESTS"}
RowsPerPage : int = 5
XpBarWidth : float = 150.0
TierBarWidth : float = 280.0

# ---------- Klick-Handler (Verse hat keine Lambdas, daher kleine Klassen) ----------

tab_click := class:
    Hud : mansion_hud
    Tab : int
    OnClick(Msg:widget_message):void = Hud.SelectTab(Tab)

page_click := class:
    Hud : mansion_hud
    Delta : int
    OnClick(Msg:widget_message):void = Hud.ChangePage(Delta)

action_click := class:
    Hud : mansion_hud
    Action : int
    OnClick(Msg:widget_message):void = Hud.DoAction(Action)

close_click := class:
    Hud : mansion_hud
    OnClick(Msg:widget_message):void = Hud.CloseMenu()

# ---------- HUD ----------

mansion_hud := class:
    Plot : mansion_plot_device
    PlayerRef : player

    CashText : text_block = text_block{DefaultTextColor := TextColor}
    IncomeText : text_block = text_block{DefaultTextColor := TextColor}
    ValueText : text_block = text_block{DefaultTextColor := TextColor}
    LevelText : text_block = text_block{DefaultTextColor := TextColor}
    XpText : text_block = text_block{DefaultTextColor := MutedColor}
    XpFill : color_block = color_block{DefaultColor := GoldColor, DefaultOpacity := 1.0, DefaultDesiredSize := vector2{X := 0.0, Y := 6.0}}

    TierText : text_block = text_block{DefaultTextColor := GoldColor}
    BigValueText : text_block = text_block{DefaultTextColor := TextColor}
    RankText : text_block = text_block{DefaultTextColor := GoldColor}
    TierFill : color_block = color_block{DefaultColor := GoldColor, DefaultOpacity := 1.0, DefaultDesiredSize := vector2{X := 0.0, Y := 8.0}}
    NextText : text_block = text_block{DefaultTextColor := MutedColor}
    CollectionText : text_block = text_block{DefaultTextColor := MutedColor}

    ToastText : text_block = text_block{DefaultTextColor := TextColor}

    var MaybeRoot : ?canvas = false
    var MaybeToast : ?overlay = false
    var MaybeMenu : ?canvas = false
    var CurrentTab : int = 0
    var CurrentPage : int = 0
    var ToastQueue : []string = array{}
    var Active : logic = false

    Show():void =
        if (UI := GetPlayerUI[PlayerRef]):
            Root := BuildRoot()
            UI.AddWidget(Root)
            set MaybeRoot = option{Root}
            set Active = true
            Refresh()
            spawn{ ToastLoop() }

    Hide():void =
        set Active = false
        CloseMenu()
        if (UI := GetPlayerUI[PlayerRef], Root := MaybeRoot?):
            UI.RemoveWidget(Root)
        set MaybeRoot = false

    Toast(Text:string):void =
        # Maximal 4 Meldungen in der Warteschlange, aeltere fallen weg.
        if (ToastQueue.Length >= 4):
            var Rest : []string = array{}
            for (I -> S : ToastQueue, I > 0):
                set Rest += array{S}
            set ToastQueue = Rest
        set ToastQueue += array{Text}

    ToastLoop()<suspends>:void =
        loop:
            if (not Active?):
                break
            if (First := ToastQueue[0]):
                var Rest : []string = array{}
                for (I -> S : ToastQueue, I > 0):
                    set Rest += array{S}
                set ToastQueue = Rest
                ToastText.SetText(S2M(First))
                if (Box := MaybeToast?):
                    Box.SetVisibility(widget_visibility.Visible)
                Sleep(2.6)
            else:
                if (Box := MaybeToast?):
                    Box.SetVisibility(widget_visibility.Collapsed)
                Sleep(0.25)

    Label(Text:string):text_block =
        text_block{DefaultText := S2M(Text), DefaultTextColor := GoldColor}

    StatSlot(Title:string, Value:text_block):stack_box_slot =
        stack_box_slot:
            Padding := margin{Left := 18.0, Right := 18.0}
            VerticalAlignment := vertical_alignment.Center
            Widget := stack_box:
                Orientation := orientation.Vertical
                Slots := array:
                    stack_box_slot:
                        Widget := Label(Title)
                        HorizontalAlignment := horizontal_alignment.Center
                    stack_box_slot:
                        Widget := Value
                        HorizontalAlignment := horizontal_alignment.Center

    Bar(Fill:color_block, Width:float, Height:float):overlay =
        overlay:
            Slots := array:
                overlay_slot:
                    Widget := color_block{DefaultColor := BarBackColor, DefaultOpacity := 1.0, DefaultDesiredSize := vector2{X := Width, Y := Height}}
                overlay_slot:
                    Widget := Fill
                    HorizontalAlignment := horizontal_alignment.Left
                    VerticalAlignment := vertical_alignment.Center

    BuildRoot():canvas =
        XpBlock := stack_box:
            Orientation := orientation.Vertical
            Slots := array:
                stack_box_slot:
                    Widget := Label("XP")
                    HorizontalAlignment := horizontal_alignment.Center
                stack_box_slot:
                    Widget := XpText
                    HorizontalAlignment := horizontal_alignment.Center
                stack_box_slot:
                    Widget := Bar(XpFill, XpBarWidth, 6.0)
                    Padding := margin{Top := 4.0}
                    HorizontalAlignment := horizontal_alignment.Center

        TopBar := overlay:
            Slots := array:
                overlay_slot:
                    Widget := color_block{DefaultColor := PanelColor, DefaultOpacity := 0.82}
                    HorizontalAlignment := horizontal_alignment.Fill
                    VerticalAlignment := vertical_alignment.Fill
                overlay_slot:
                    Widget := color_block{DefaultColor := GoldColor, DefaultOpacity := 1.0, DefaultDesiredSize := vector2{X := 10.0, Y := 2.0}}
                    HorizontalAlignment := horizontal_alignment.Fill
                    VerticalAlignment := vertical_alignment.Bottom
                overlay_slot:
                    Padding := margin{Left := 14.0, Right := 14.0, Top := 10.0, Bottom := 12.0}
                    Widget := stack_box:
                        Orientation := orientation.Horizontal
                        Slots := array:
                            StatSlot("CASH", CashText)
                            StatSlot("INCOME / MIN", IncomeText)
                            StatSlot("MANSION VALUE", ValueText)
                            StatSlot("PLAYER LEVEL", LevelText)
                            stack_box_slot:
                                Widget := XpBlock
                                Padding := margin{Left := 18.0, Right := 18.0}
                                VerticalAlignment := vertical_alignment.Center

        RightPanel := overlay:
            Slots := array:
                overlay_slot:
                    Widget := color_block{DefaultColor := PanelColor, DefaultOpacity := 0.82, DefaultDesiredSize := vector2{X := 320.0, Y := 10.0}}
                    HorizontalAlignment := horizontal_alignment.Fill
                    VerticalAlignment := vertical_alignment.Fill
                overlay_slot:
                    Widget := color_block{DefaultColor := GoldColor, DefaultOpacity := 1.0, DefaultDesiredSize := vector2{X := 3.0, Y := 10.0}}
                    HorizontalAlignment := horizontal_alignment.Left
                    VerticalAlignment := vertical_alignment.Fill
                overlay_slot:
                    Padding := margin{Left := 20.0, Right := 20.0, Top := 16.0, Bottom := 16.0}
                    Widget := stack_box:
                        Orientation := orientation.Vertical
                        Slots := array:
                            stack_box_slot:
                                Widget := Label("YOUR ESTATE")
                            stack_box_slot:
                                Widget := TierText
                                Padding := margin{Bottom := 10.0}
                            stack_box_slot:
                                Widget := Label("MANSION VALUE")
                            stack_box_slot:
                                Widget := BigValueText
                            stack_box_slot:
                                Widget := RankText
                                Padding := margin{Bottom := 12.0}
                            stack_box_slot:
                                Widget := Label("NEXT HOME")
                            stack_box_slot:
                                Widget := Bar(TierFill, TierBarWidth, 8.0)
                                Padding := margin{Top := 4.0, Bottom := 6.0}
                            stack_box_slot:
                                Widget := NextText
                                Padding := margin{Bottom := 12.0}
                            stack_box_slot:
                                Widget := Label("COLLECTION")
                            stack_box_slot:
                                Widget := CollectionText
                                Padding := margin{Bottom := 10.0}
                            stack_box_slot:
                                Widget := text_block{DefaultText := S2M("Use the Estate Tablet to build"), DefaultTextColor := MutedColor}

        ToastBox := overlay:
            Slots := array:
                overlay_slot:
                    Widget := color_block{DefaultColor := PanelColor, DefaultOpacity := 0.9}
                    HorizontalAlignment := horizontal_alignment.Fill
                    VerticalAlignment := vertical_alignment.Fill
                overlay_slot:
                    Widget := color_block{DefaultColor := GoldColor, DefaultOpacity := 1.0, DefaultDesiredSize := vector2{X := 10.0, Y := 2.0}}
                    HorizontalAlignment := horizontal_alignment.Fill
                    VerticalAlignment := vertical_alignment.Top
                overlay_slot:
                    Widget := ToastText
                    Padding := margin{Left := 26.0, Right := 26.0, Top := 12.0, Bottom := 12.0}
                    HorizontalAlignment := horizontal_alignment.Center
        ToastBox.SetVisibility(widget_visibility.Collapsed)
        set MaybeToast = option{ToastBox}

        canvas:
            Slots := array:
                canvas_slot:
                    Anchors := anchors{Minimum := vector2{X := 0.5, Y := 0.0}, Maximum := vector2{X := 0.5, Y := 0.0}}
                    Alignment := vector2{X := 0.5, Y := 0.0}
                    Offsets := margin{Left := 0.0, Top := 14.0, Right := 0.0, Bottom := 0.0}
                    SizeToContent := true
                    Widget := TopBar
                canvas_slot:
                    Anchors := anchors{Minimum := vector2{X := 1.0, Y := 0.5}, Maximum := vector2{X := 1.0, Y := 0.5}}
                    Alignment := vector2{X := 1.0, Y := 0.5}
                    Offsets := margin{Left := -24.0, Top := 0.0, Right := 0.0, Bottom := 0.0}
                    SizeToContent := true
                    Widget := RightPanel
                canvas_slot:
                    Anchors := anchors{Minimum := vector2{X := 0.5, Y := 0.0}, Maximum := vector2{X := 0.5, Y := 0.0}}
                    Alignment := vector2{X := 0.5, Y := 0.0}
                    Offsets := margin{Left := 0.0, Top := 118.0, Right := 0.0, Bottom := 0.0}
                    SizeToContent := true
                    ZOrder := 5
                    Widget := ToastBox

    Refresh():void =
        Value := Plot.MansionValue()
        PL := Plot.PlayerLevel()
        Into := Plot.XpIntoLevel()
        Need := XpToNext(PL)
        CashText.SetText(S2M(FormatMoney(Plot.Cash)))
        IncomeText.SetText(S2M("+{FormatMoney(Plot.IncomePerMinute())}"))
        ValueText.SetText(S2M(FormatMoney(Value)))
        LevelText.SetText(S2M("LVL {PL}"))
        XpText.SetText(S2M("{Into} / {Need}"))
        XpFill.SetDesiredSize(vector2{X := XpBarWidth * Ratio(Into, Need), Y := 6.0})
        TierText.SetText(S2M("{Plot.TierName(Plot.Tier)}   ({Plot.Tier}/{MaxTier})"))
        BigValueText.SetText(S2M(FormatFull(Value)))
        RankText.SetText(S2M("MANSION RANK  #{RankFor(Value)}"))
        TierFill.SetDesiredSize(vector2{X := TierBarWidth * Plot.NextTierProgress(), Y := 8.0})
        NextText.SetText(S2M(Plot.NextTierText()))
        CollectionText.SetText(S2M(Plot.CollectionText()))

    # ---------- Estate-Tablet (Menue) ----------

    OpenMenu():void =
        set CurrentPage = 0
        RebuildMenu()

    CloseMenu():void =
        if (UI := GetPlayerUI[PlayerRef], Menu := MaybeMenu?):
            UI.RemoveWidget(Menu)
        set MaybeMenu = false

    IsMenuOpen():logic =
        if (MaybeMenu?) then true else false

    RefreshMenu():void =
        if (MaybeMenu?):
            RebuildMenu()

    SelectTab(Tab:int):void =
        set CurrentTab = Tab
        set CurrentPage = 0
        RebuildMenu()

    ChangePage(Delta:int):void =
        set CurrentPage += Delta
        RebuildMenu()

    DoAction(Action:int):void =
        if (Action = -1):
            Plot.TryUpgradeTier(PlayerRef)
        else if (Action >= 0):
            Plot.TryBuy(PlayerRef, Action)

    RebuildMenu():void =
        if (UI := GetPlayerUI[PlayerRef]):
            if (Old := MaybeMenu?):
                UI.RemoveWidget(Old)
            Menu := BuildMenu()
            UI.AddWidget(Menu, player_ui_slot{InputMode := ui_input_mode.All})
            set MaybeMenu = option{Menu}

    BuildMenu():canvas =
        # Linke Navigation
        Nav := stack_box{Orientation := orientation.Vertical, Slots := array{}}
        for (I -> Name : TabNames):
            Text := if (I = CurrentTab) then "> {Name}" else Name
            Button := button_regular{DefaultText := S2M(Text)}
            Handler := tab_click{Hud := Self, Tab := I}
            Button.OnClick().Subscribe(Handler.OnClick)
            Nav.AddWidget(stack_box_slot{Widget := Button, Padding := margin{Bottom := 6.0}, HorizontalAlignment := horizontal_alignment.Fill})
        CloseButton := button_quiet{DefaultText := S2M("CLOSE")}
        CloseHandler := close_click{Hud := Self}
        CloseButton.OnClick().Subscribe(CloseHandler.OnClick)
        Nav.AddWidget(stack_box_slot{Widget := CloseButton, Padding := margin{Top := 20.0}, HorizontalAlignment := horizontal_alignment.Fill})

        # Inhalt
        Rows := Plot.RowsForTab(CurrentTab)
        Pages := Max(1, ToInt(((Rows.Length + RowsPerPage - 1) * 1.0) / (RowsPerPage * 1.0)))
        if (CurrentPage >= Pages) then set CurrentPage = Pages - 1
        if (CurrentPage < 0) then set CurrentPage = 0
        Title := if (N := TabNames[CurrentTab]) then N else ""

        Content := stack_box{Orientation := orientation.Vertical, Slots := array{}}
        Content.AddWidget(stack_box_slot{Widget := Label("ESTATE TABLET  /  {Title}"), Padding := margin{Bottom := 4.0}})
        Content.AddWidget(stack_box_slot{
            Widget := text_block{DefaultText := S2M(Plot.TabHeader(CurrentTab)), DefaultTextColor := TextColor},
            Padding := margin{Bottom := 14.0}})

        if (Rows.Length = 0):
            Content.AddWidget(stack_box_slot{
                Widget := text_block{DefaultText := S2M("Nothing here right now. Upgrade your home to unlock more."), DefaultTextColor := MutedColor}})

        Start := CurrentPage * RowsPerPage
        for (I -> Row : Rows, I >= Start, I < Start + RowsPerPage):
            Content.AddWidget(stack_box_slot{Widget := BuildRow(Row), Padding := margin{Bottom := 8.0}, HorizontalAlignment := horizontal_alignment.Fill})

        Prev := button_quiet{DefaultText := S2M("< PREV")}
        PrevHandler := page_click{Hud := Self, Delta := -1}
        Prev.OnClick().Subscribe(PrevHandler.OnClick)
        if (CurrentPage <= 0) then Prev.SetEnabled(false)
        Next := button_quiet{DefaultText := S2M("NEXT >")}
        NextHandler := page_click{Hud := Self, Delta := 1}
        Next.OnClick().Subscribe(NextHandler.OnClick)
        if (CurrentPage >= Pages - 1) then Next.SetEnabled(false)
        Pager := stack_box:
            Orientation := orientation.Horizontal
            Slots := array:
                stack_box_slot:
                    Widget := Prev
                stack_box_slot:
                    Widget := text_block{DefaultText := S2M("Page {CurrentPage + 1} / {Pages}   |   Cash {FormatMoney(Plot.Cash)}"), DefaultTextColor := MutedColor}
                    Padding := margin{Left := 16.0, Right := 16.0}
                    VerticalAlignment := vertical_alignment.Center
                stack_box_slot:
                    Widget := Next
        Content.AddWidget(stack_box_slot{Widget := Pager, Padding := margin{Top := 6.0}})

        Panel := overlay:
            Slots := array:
                overlay_slot:
                    Widget := color_block{DefaultColor := PanelColor, DefaultOpacity := 0.95, DefaultDesiredSize := vector2{X := 1120.0, Y := 660.0}}
                overlay_slot:
                    Widget := color_block{DefaultColor := GoldColor, DefaultOpacity := 1.0, DefaultDesiredSize := vector2{X := 1120.0, Y := 3.0}}
                    HorizontalAlignment := horizontal_alignment.Fill
                    VerticalAlignment := vertical_alignment.Top
                overlay_slot:
                    Padding := margin{Left := 28.0, Top := 26.0, Right := 28.0, Bottom := 22.0}
                    HorizontalAlignment := horizontal_alignment.Fill
                    VerticalAlignment := vertical_alignment.Top
                    Widget := stack_box:
                        Orientation := orientation.Horizontal
                        Slots := array:
                            stack_box_slot:
                                Widget := Nav
                                VerticalAlignment := vertical_alignment.Top
                                Padding := margin{Right := 28.0}
                            stack_box_slot:
                                Widget := Content
                                VerticalAlignment := vertical_alignment.Top

        canvas:
            Slots := array:
                canvas_slot:
                    Anchors := anchors{Minimum := vector2{X := 0.5, Y := 0.5}, Maximum := vector2{X := 0.5, Y := 0.5}}
                    Alignment := vector2{X := 0.5, Y := 0.5}
                    Offsets := margin{Left := 0.0, Top := 40.0, Right := 0.0, Bottom := 0.0}
                    SizeToContent := true
                    ZOrder := 10
                    Widget := Panel

    BuildRow(Row:menu_row):overlay =
        Box := overlay:
            Slots := array:
                overlay_slot:
                    Widget := color_block{DefaultColor := RowColor, DefaultOpacity := 0.95, DefaultDesiredSize := vector2{X := 820.0, Y := 82.0}}
                overlay_slot:
                    Widget := text_block{DefaultText := S2M(Row.Info), DefaultTextColor := TextColor}
                    Padding := margin{Left := 18.0, Top := 8.0, Right := 220.0, Bottom := 8.0}
                    HorizontalAlignment := horizontal_alignment.Left
                    VerticalAlignment := vertical_alignment.Center
        if (Row.HasButton?):
            Button := button_loud{DefaultText := S2M(Row.ButtonLabel)}
            Handler := action_click{Hud := Self, Action := Row.Action}
            Button.OnClick().Subscribe(Handler.OnClick)
            if (not Row.Enabled?) then Button.SetEnabled(false)
            Box.AddWidget(overlay_slot{Widget := Button, Padding := margin{Right := 14.0}, HorizontalAlignment := horizontal_alignment.Right, VerticalAlignment := vertical_alignment.Center})
        Box
