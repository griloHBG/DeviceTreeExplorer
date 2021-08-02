class SearchHitPastelColor:
    pastel_colors_dark = [    '#3436bf',
                              '#074602',
                              '#398933',
                              '#73A498',
                              '#317354',
                              '#2a68ae',
                              '#b1a24a',
                              '#2b52a4',
                              '#316269',
                              '#5b8dac',
                              '#690f97',
                              '#6b3f34',
                              '#7f64ef',
                              '#884836',
                              '#b1a421',
                              '#4fb093',]

    color_amount = len(pastel_colors_dark)
    current_color_index = 0
    @classmethod
    def get_hex_color(cls):
        index = cls.current_color_index
        cls.current_color_index+=1
        if cls.current_color_index == cls.color_amount:
            cls.current_color_index = 0
        return cls.pastel_colors_dark[index]
