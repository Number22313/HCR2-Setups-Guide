"""Sqlalchemy tools"""
from flask import Flask, render_template, request, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.exceptions import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import aliased
from sqlalchemy.exc import SQLAlchemyError

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = 'temporary_secret_key'
db = SQLAlchemy(app)


class Setups(db.Model):
    """Main junction table, different combinations of times,tracks,tunes,vehicles,and parts"""
    __tablename__ = "Setups"
    setup_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    time_id = db.Column(db.Integer, db.ForeignKey("WR_Times.time_id"), nullable=False)
    track_id = db.Column(db.Integer, db.ForeignKey("Tracks.track_id"), nullable=False)
    tune_id = db.Column(db.Integer, db.ForeignKey("Tunes.tune_id"), nullable=False)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("Vehicles.vehicle_id"), nullable=False)
    part_id = db.Column(db.Integer, db.ForeignKey("Part_Combinations.part_id"), nullable=False)
    wr_time = db.relationship("WR_Times", back_populates="setups")
    track = db.relationship("Tracks", back_populates="setups")
    tune = db.relationship("Tunes", back_populates="setups")
    vehicle = db.relationship("Vehicles", back_populates="setups")
    parts_combinations = db.relationship("Parts", back_populates="setups")

class WRTimes(db.Model):
    """All of the different player and time combinations"""
    __tablename__ = "WR_Times"
    time_id = db.Column(db.Integer, primary_key=True, autoincrement=True, nullable=False)
    time = db.Column(db.REAL, nullable=False)
    player = db.Column(db.Text, nullable=False)
    setups = db.relationship("Setups", back_populates="wr_time")

class Tracks(db.Model):
    """All of the tracks"""
    __tablename__ = "Tracks"
    track_id = db.Column(db.Integer,
                         primary_key=True,
                         autoincrement=True,
                         nullable=False,
                         unique=True)
    track_name = db.Column(db.Text, nullable=False)
    setups = db.relationship("Setups", back_populates="track")

class Tunes(db.Model):
    """All of the different tune combinations"""
    __tablename__ = "Tunes"
    tune_id = db.Column(db.Integer,
                        primary_key=True,
                        autoincrement=True,
                        nullable=False,
                        unique=True)
    tune1 = db.Column(db.Integer, nullable=False)
    tune2 = db.Column(db.Integer, nullable=False)
    tune3 = db.Column(db.Integer, nullable=False)
    tune4 = db.Column(db.Integer, nullable=False)
    setups = db.relationship("Setups", back_populates="tune")

class Vehicles(db.Model):
    """All of the vehicles"""
    __tablename__ = "Vehicles"
    vehicle_id = db.Column(db.Integer,
                           primary_key=True,
                           autoincrement=True,
                           nullable=False,
                           unique=True)
    vehicle_name = db.Column(db.Text, unique=True)
    setups = db.relationship("Setups", back_populates="vehicle")

class Parts(db.Model):
    """All of the different part combinations"""
    __tablename__ = "Part_Combinations"
    part_id = db.Column(db.Integer,
                        primary_key=True,
                        autoincrement=True,
                        nullable=False,
                        unique=True)
    slot1 = db.Column(db.Text, nullable=False)
    slot2 = db.Column(db.Text, nullable=False)
    slot3 = db.Column(db.Text, nullable=False)
    setups = db.relationship("Setups", back_populates="parts_combinations")


@app.errorhandler(HTTPException)
def error_handler(a):
    """Error handler for every error between 400 and 500"""
    return render_template('error.html', error_code=a.code, error_response=a.name)


def wr_subquery():
    """Subquery of Setups that returns a table with only
      the fastest times (wrs) and can then be filtered more"""
    #World Record setups
    setup_subquery = aliased(Setups)
    subquery = (db.session.query(func.min(WRTimes.time))
                    .join(setup_subquery, WRTimes.time_id == setup_subquery.time_id)
                    .filter(setup_subquery.track_id == Setups.track_id,
                            setup_subquery.vehicle_id == Setups.vehicle_id)
                    .scalar_subquery())
    return Setups.query.join(WRTimes).filter(WRTimes.time == subquery)


@app.before_request
def settings_menu():
    """Settings handler that runs before the page loads, saves user settings in session"""
    error = []
    rpp = request.form.get('rows_per_page', "")
    theme = request.form.get('theme', "")
    if 'theme' not in session:
        session['theme'] = 'dark'
    if 'rows_per_page' not in session:
        session['rows_per_page'] = 50

    #updates settings with the new values or reverts to default values
    if request.method == 'POST' and 'Save' in request.form:
        #validation

        #light/dark theme check
        if theme and theme == 'dark':
            session['theme'] = 'dark'
        else:
            session['theme'] = 'light'

        #checks if the values saved are valid
        try:
            rpp = int(rpp)
            if 0 < rpp < 101:
                session['rows_per_page'] = rpp
            else:
                session['rows_per_page'] = 50
                error.append("Rows per page must be between 1 and 100")

        #catches anything that isnt an integer
        except (ValueError,TypeError):
            session['rows_per_page'] = 50
            if rpp != "":
                error.append(f"{rpp} is not a number")

        #returns the error message
        if error:
            session['settings_error'] = error
        return redirect(request.referrer or url_for('Home'))


@app.route('/', methods=['GET', 'POST'])
def home():
    """Main home page, mostly displays small statistics/facts and information"""

    #total unique setups, parts and players
    setups_count = Setups.query.count()
    total_parts = Parts.query.count()
    total_players = len({i.player for i in WRTimes.query.all()})

    #sorts all players from fastest to slowest time
    fastest_times = Setups.query.join(WRTimes).order_by(WRTimes.time.asc()).all()
    return render_template('home.html',
                           active_page='Home',
                           setups_count=setups_count,
                           total_parts=total_parts,
                           total_players=total_players,
                           fastest_times=fastest_times)


@app.route('/Setups', methods=['GET', 'POST'])
def setups():
    """Setups page, handles inserting and deleting data
      (with validation) from the database as well as
        showing the data."""
    insert_errors = []

    #list of all tracks, vehicles, and parts for less filtering code
    global_tracks_list=[t.track_name for t in Tracks.query.all()]
    global_vehicles_list=[v.vehicle_name for v in Vehicles.query.all()]
    global_parts_list=({p.slot1 for p in Parts.query.all()}|
                       {p.slot2 for p in Parts.query.all()}|
                       {p.slot3 for p in Parts.query.all()})
    if request.method == 'POST':
        #checks if the setup is being deleted or inserted
        if 'setup_delete' in request.form:
            setup_delete = request.form.get('setup_delete')
            try:
                #looks up the setup id and deletes it only if it exists
                setup_delete = int(setup_delete)
                Setups.query.filter(Setups.setup_id == setup_delete).delete()
                db.session.commit()

            except SQLAlchemyError:
                #cancels the deletion if no setups exist
                db.session.rollback()
                insert_errors.append("Database error, insert rolled back")

            except ValueError:
                #catches any ids that arent integers
                insert_errors.append(f"{setup_delete} is not a valid id")

        #checks if the setup is being deleted or inserted
        if 'insert' in request.form:
            insert_submit = request.form.get("insert")
            if insert_submit == "insert":
                print("Inserting")

                #all form fields as variables for validation and insertion with fallback values
                not_valid = False
                time=request.form.get("time","")
                player=request.form.get("player","")
                track_name=request.form.get("track_name","")
                tune1=request.form.get("tune1","")
                tune2=request.form.get("tune2","")
                tune3=request.form.get("tune3","")
                tune4=request.form.get("tune4","")
                try: #converts tunes to a list for easier validation
                    tune1 = int(tune1)
                    tune2 = int(tune2)
                    tune3 = int(tune3)
                    tune4 = int(tune4)
                except (TypeError,ValueError):
                    not_valid = True
                    tune1,tune2,tune3,tune4 = 0,0,0,0
                tunes_list = [tune1,tune2,tune3,tune4]
                vehicle_name=request.form.get("vehicle_name","")
                slot_list = sorted([request.form.get("slot1",""),
                                    request.form.get("slot2",""),
                                    request.form.get("slot3","")
                                    ])
                slot1,slot2,slot3 = slot_list
                print(f"{slot_list}")

                #back end validation

                #tries to validate all of the input fields and catches empty ones,
                #checks every part,track, and vehicle being inserted to see if it exists in the DB
                if (not time or not player or not track_name or not vehicle_name
                    or not slot1 or not slot2 or not slot3):
                    insert_errors.append("Not all fields are filled")
                    not_valid = True

                #checks if the track actually exists/is valid
                if track_name and not Tracks.query.filter_by(track_name=track_name).first():
                    insert_errors.append(f"{track_name} is not a valid track")
                    not_valid = True

                if time:
                    try:
                        time = float(time)
                        print(time)
                        #in game time is limited to the 32 bit integer limit
                        if time <= 0 or time >= 2147483647:
                            insert_errors.append(f"{time} is not a valid time")
                            not_valid = True
                    except(ValueError, TypeError):
                        insert_errors.append(f"{time} is not a number")
                        not_valid = True


                if any(not o for o in tunes_list):
                    insert_errors.append("Not all tunes fields are full")
                    not_valid=True
                else:
                    for o in tunes_list:
                        try:
                            o = int(o)
                            #in game tunes can only be at level 1-20
                            if o >= 21 or o <= 0:
                                insert_errors.append(f"{o} is not a valid tune")
                                not_valid = True
                        except ValueError:
                            insert_errors.append(f"{o} is not a number")
                            not_valid = True

                #checks if the vehicle actually exists/is valid
                if vehicle_name and not Vehicles.query.filter_by(
                    vehicle_name=vehicle_name).first():
                    insert_errors.append(f"{vehicle_name} is not a valid vehicle")
                    not_valid = True

                #checks if the parts actually exist/are valid
                if slot_list:
                    for i in slot_list:
                        if i and not Parts.query.filter(
                            (Parts.slot1==i)|
                            (Parts.slot2==i)|
                            (Parts.slot3==i)).first():
                            insert_errors.append(f"{i} is not a valid part")
                            not_valid = True

                #in game you cannot have the same part in more than one slot
                if slot1 and slot2 and slot3:
                    if len({slot1,slot2,slot3}) < 3:
                        insert_errors.append("Duplicate parts")
                        not_valid = True

                #in game max and min character limit for names
                if player and (len(player) > 16 or len(player) < 3):
                    insert_errors.append(f"{player} is not a real player")
                    not_valid = True


                if not_valid:
                    insert_errors.append("Invalid Fields")
                else:
                    #only inserts if nothing is caught by the validation
                    try:
                        #DB search for existing setups
                        vehicle_query = Vehicles.query.filter_by(vehicle_name=vehicle_name).first()
                        if not vehicle_query:
                            vehicle_query = Vehicles(vehicle_name=vehicle_name)
                            db.session.add(vehicle_query)

                        track_query = Tracks.query.filter_by(track_name=track_name).first()
                        if not track_query:
                            track_query = Tracks(track_name=track_name)
                            db.session.add(track_query)

                        tune_query = Tunes.query.filter_by(tune1=tune1,
                                                           tune2=tune2,
                                                           tune3=tune3,
                                                           tune4=tune4).first()
                        if not tune_query:
                            tune_query = Tunes(tune1=tune1,
                                               tune2=tune2,
                                               tune3=tune3,
                                               tune4=tune4)
                            db.session.add(tune_query)

                        parts_query = Parts.query.filter_by(slot1=slot1,
                                                            slot2=slot2,
                                                            slot3=slot3).first()
                        if not parts_query:
                            parts_query = Parts(slot1=slot1, slot2=slot2, slot3=slot3)
                            db.session.add(parts_query)

                        player_query = WRTimes.query.filter(WRTimes.player.ilike(player)).first()
                        if player_query:
                            player = player_query.player

                        db.session.flush()

                        #checking if they match an existing setup
                        setup_query = Setups.query.join(WRTimes).filter(
                            Setups.vehicle == vehicle_query,
                            Setups.track == track_query,
                            Setups.tune == tune_query,
                            Setups.parts_combinations == parts_query,
                            WRTimes.player == player
                        ).first()

                        #updating the time of the existing seutp
                        if setup_query:
                            print("Already a setup")
                            if time < setup_query.wr_time.time:
                                if not insert_errors:
                                    insert_errors.append("Updated")
                                setup_query.wr_time.time = time

                        #new setup so it can be created
                        elif not setup_query:
                            print("Doesnt exist yet")
                            time_query = WRTimes(time=time,player=player)
                            db.session.add(time_query)

                            db.session.flush()

                            setup = Setups(
                                time_id = time_query.time_id,
                                vehicle_id = vehicle_query.vehicle_id,
                                track_id = track_query.track_id,
                                tune_id = tune_query.tune_id,
                                part_id = parts_query.part_id
                            )

                            db.session.add(setup)
                            if not insert_errors:
                                insert_errors.append("Inserted")

                        db.session.commit()

                    #catches any erorrs while inserting
                    except SQLAlchemyError:
                        db.session.rollback()
                        insert_errors.append("Database error, insert rolled back")

    all_setups = reversed(Setups.query.all())
    return render_template('Setups.html',
                           active_page='setups',
                           setups=all_setups,
                           tracks_list=global_tracks_list,
                           vehicles_list=global_vehicles_list,
                           parts_list=global_parts_list,
                           insert_errors=insert_errors)


@app.route('/Search', methods=['GET', 'POST'])
def search():
    """Search page, displays setups from the database
      that are filtered by the search bar and checkbox filters"""

    #linked to the clear filters button and
    # clears all input fields back to default
    if request.args.get("clear_filters"):
        return redirect(url_for('search'))
    setup = []
    result_errors = []
    wr_setups = []

    #all of the variables fallback for none because
    # the first time the page is loaded there are no arguments to fetch
    time = request.args.get("time") or None
    tune1 = request.args.get("tune1") or None
    tune2 = request.args.get("tune2") or None
    tune3 = request.args.get("tune3") or None
    tune4 = request.args.get("tune4") or None
    tunes = [(tune1, Tunes.tune1),
            (tune2, Tunes.tune2),
            (tune3, Tunes.tune3),
            (tune4, Tunes.tune4)]
    wr_checked = request.args.get("wr_checked") or None
    player_filter = request.args.getlist("player_filter") or None
    track_filter = request.args.getlist("track_filter") or None
    vehicle_filter = request.args.getlist("vehicle_filter") or None
    slot1 = request.args.getlist("slot1")
    slot2 = request.args.getlist("slot2")
    slot3 = request.args.getlist("slot3")

    #lists for all tracks, vehicles, and parts so
    # there is less repetetive code in the validation
    global_tracks_list=[t.track_name for t in Tracks.query.all()]
    global_vehicles_list=[v.vehicle_name for v in Vehicles.query.all()]
    global_parts_list=({p.slot1 for p in Parts.query.all()}|
                    {p.slot2 for p in Parts.query.all()}|
                    {p.slot3 for p in Parts.query.all()})

    #Seperate variables to keep filters when reloading page
    filters = [time,tune1,tune2,tune3,tune4,
               slot1,slot2,slot3,wr_checked,
               player_filter,track_filter,vehicle_filter]

    #set that only has players with active times in setups
    players_options = sorted(
        {c.wr_time.player for c in Setups.query.all()
         if c.wr_time and c.wr_time.player})

    search_bar = request.args.get("search_bar") or None

    setup = (Setups.query.join(WRTimes)
             .join(Vehicles)
             .join(Tracks)
             .join(Tunes)
             .join(Parts)
             .order_by(WRTimes.time.asc()))

    #checks if the filters are being used so only setups
    # with actual inputs in the filters are checked
    if vehicle_filter:
        vehicle = [v for v in vehicle_filter if v in global_vehicles_list]
        setup = setup.filter(Vehicles.vehicle_name.in_(vehicle))

        vehicle_invalid = [v for v in vehicle_filter if v not in global_vehicles_list]
        for v in vehicle_invalid:
            result_errors.append(f"{v} is not a valid vehicle")

    if time:
        try:
            time = float(time)
            if time > 0:
                setup = setup.filter(WRTimes.time == time)
            else:
                result_errors.append("time must be greater than 0")
        except ValueError:
            result_errors.append(f"{time} is not a number")

    if player_filter:
        player = [p for p in player_filter if p in players_options]
        setup = setup.filter(WRTimes.player.in_(player))

        #catches players that dont exist or are orphans
        player_invalid = [p for p in player_filter if p not in players_options]
        for p in player_invalid:
            result_errors.append(f"{p} player has no setups")

    if track_filter:
        track = [t for t in track_filter if t in global_tracks_list]
        setup = setup.filter(Tracks.track_name.in_(track))

        track_invalid = [t for t in track_filter if t not in global_tracks_list]
        for t in track_invalid:
            result_errors.append(f"{t} is not a valid track")

    for value,column in tunes:
        if value:
            try:
                value = int(value)
                #in game limits are level 1-20
                if 21 > value > 0:
                    setup = setup.filter(column == value)
                else:
                    result_errors.append(f"{value} is not between 1 and 20")
            except ValueError:
                result_errors.append(f"{value} is not an integer")

    #checks the slots 1 by 1 to make the
    # order of the combination irrelevant
    for slot1_ in slot1:
        if slot1_ in global_parts_list:
            setup = setup.filter((Parts.slot1 == slot1_)|
                                (Parts.slot2 == slot1_)|
                                (Parts.slot3 == slot1_))
        else:
            result_errors.append(f"{slot1_} is not a valid part")

    for slot2_ in slot2:
        if slot2_ in global_parts_list:
            setup = setup.filter((Parts.slot1 == slot2_)|
                                (Parts.slot2 == slot2_)|
                                (Parts.slot3 == slot2_))
        else:
            result_errors.append(f"{slot2_} is not a valid part")

    for slot3_ in slot3:
        if slot3_ in global_parts_list:
            setup = setup.filter((Parts.slot1 == slot3_)|
                                (Parts.slot2 == slot3_)|
                                (Parts.slot3 == slot3_))
        else:
            result_errors.append(f"{slot3_} is not a valid part")

    master_list_lower = {}
    for z in (global_tracks_list+global_vehicles_list+global_parts_list+players_options):
        master_list_lower[z.lower()] = z

    #again only filtering if the search bar is being used
    if search_bar:
        #turns the search into word combinations (2 words to X words)
        loop_index = 0
        search_split = search_bar.strip().split()
        filter_match = []
        length = len(search_split)
        while loop_index < len(search_split):
            match = False
            for search_length in range(length,1,-1):
                if loop_index + search_length <= len(search_split):
                    word = " ".join(search_split[loop_index:loop_index+search_length])
                    if word.lower() in (master_list_lower):
                        loop_index += search_length
                        match = True
                        filter_match.append(master_list_lower[word.lower()])
                        break

            #remaining word saved as itself
            if not match:
                filter_match.append(search_split[loop_index])
                loop_index += 1


        #.ilike ignores case sensitivity so results are more accurate
        for c in filter_match:
            search_filter = [Tracks.track_name.ilike(c),
                      Vehicles.vehicle_name.ilike(c),
                      WRTimes.player.ilike(c),
                      Parts.slot1.ilike(c),
                      Parts.slot2.ilike(c),
                      Parts.slot3.ilike(c)]

            #integer filters can only be checked for being negative or not
            try:
                search_time = float(c)
                if search_time > 0:
                    search_filter.append(WRTimes.time == search_time)
                else:
                    result_errors.append(f"(search) {search_time} cannot be negative")
            except ValueError:
                pass

            try:
                search_tune = int(c)
                if search_tune > 0:
                    search_filter.extend([Tunes.tune1 == search_tune,
                                Tunes.tune2 == search_tune,
                                Tunes.tune3 == search_tune,
                                Tunes.tune4 == search_tune])
                else:
                    result_errors.append(f"(search) {search_tune} cannot be negative")
            except ValueError:
                pass

            setup = setup.filter(or_(*search_filter))

    #filters the results further by  only including the fastest
    # times with a specific vehicle and track combination
    if wr_checked:
        wrs = wr_subquery().subquery()
        setup = setup.filter(Setups.setup_id.in_(db.session.query(wrs.c.setup_id)))

    #returns nothing if any filter is invalid
    if result_errors:
        result = []
    else:
        result = setup.all()

        if wr_checked:
            for i in result:
                wr_setups.append(int(i.setup_id))
            print(f"{wr_setups}")

    return render_template('Search.html',
                           active_page='search',
                           tracks_list=global_tracks_list,
                           vehicles_list=global_vehicles_list,
                           parts_list=global_parts_list,
                           search_bar=search_bar or "",
                           result=result,
                           players=players_options,
                           result_errors=result_errors,
                           filters=filters or "")


@app.route('/Leaderboards', methods=['GET', 'POST'])
def leaderboards():
    """Leaderboards page, displays players with the
      most world records attributed to their name"""
    all_setups = Setups.query.all()

    #list that only contains players with world records
    wr = wr_subquery().all()

    wr_count = []
    for z in wr:
        wr_count.append(z.wr_time.player)

    wr_count_lower = []
    for x in wr_count:
        wr_count_lower.append(x.lower())

    player_wr_count = []
    unique_players = set()

    #adds the player and number of world records,
    # but only loops through each player once
    for i in wr_count:
        player = i.lower()
        if player not in unique_players:
            wrs = wr_count_lower.count(player)
            player_wr_count.append((wrs, i))
            unique_players.add(player)

    player_wr_count.sort(reverse=True)

    #list that counts how many times a part
    # combination appears in the database
    all_parts = []
    for a in all_setups:
        all_parts.append(a.part_id)

    parts_count = []
    unique_parts = set(all_parts)
    for p in unique_parts:
        count = all_parts.count(p)
        parts_row = Parts.query.get(p)
        parts_count.append((count, p, parts_row))
    parts_count.sort(reverse=True)

    return render_template('Leaderboards.html',
                           active_page='leaderboards',
                           player_wr_count=player_wr_count,
                           parts_count=parts_count)



if __name__ == '__main__':
    app.run(debug=True)
