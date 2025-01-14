import locale

def adj_decimal_seperator(input):
    # lang = locale.getdefaultlocale()
    lang = ('de_DE', 'cp1252')
    # print(lang)

    if isinstance(input,str):
        if lang[0] == "en_US":
            return input
        elif lang[0] == "de_DE":
            return f"Position\t{str(input).replace('.',',')}"
    elif isinstance(input,float):
        if lang[0] == "en_US":
            return input
        elif lang[0] == "de_DE":
            return f"Position\t{float(input).replace('.',',')}"

if __name__ == '__main__':

    str1 = "123.456"
    float1 = 654.321
    print(adj_decimal_seperator(str1))
    print(adj_decimal_seperator(float1))