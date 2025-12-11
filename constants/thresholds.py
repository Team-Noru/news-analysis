CAP_BUCKET_THRESHOLDS = {
    "mega": {      # 초대형주 
        "RATIO_DELTA_PPT_THRESHOLD": 1.0,    # 1%p 이상 변동이면 신호
        "RATIO_REL_CHANGE_PCT_THRESHOLD": 10.0,  # 상대변화 10% 이상
        "MIN_MAJOR_RATIO_FOR_NEW_MAJOR": 10.0,   # 10% 이상이면 주요 주주로 간주
    },
    "large": {     # 대형주
        "RATIO_DELTA_PPT_THRESHOLD": 2.0,    # 2%p 이상
        "RATIO_REL_CHANGE_PCT_THRESHOLD": 15.0,
        "MIN_MAJOR_RATIO_FOR_NEW_MAJOR": 10.0,
    },
    "mid_small": {  # 중소형주
        "RATIO_DELTA_PPT_THRESHOLD": 3.0,    # 3%p 이상
        "RATIO_REL_CHANGE_PCT_THRESHOLD": 20.0,
        "MIN_MAJOR_RATIO_FOR_NEW_MAJOR": 15.0,
    },
    "unknown": {    # 시총 정보 없을 때
        "RATIO_DELTA_PPT_THRESHOLD": 2.0,
        "RATIO_REL_CHANGE_PCT_THRESHOLD": 15.0,
        "MIN_MAJOR_RATIO_FOR_NEW_MAJOR": 10.0,
    },
}