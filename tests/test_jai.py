from phenomate_core import JaiPreprocessor


input_dir ='/home/jbowden/APPN/repos/phenomate_data/Amiga/UM_Tests/um4_remove-dash/jai1/'
input_file ='2026-02-17_12-34-47_171789_+1030_um1_jai1.bin'  



input_dir ='/home/jbowden/APPN/repos/phenomate_data/Amiga/UM_Tests/raw/um_test_2/jai1'
input_file ='2026-02-10_12-11-52_212631_+1030_test-bar2_jai1.bin'


# 1477631406 bytes == 119 images and 76 bytes
# serailized_image length: 12417059
# Declared length        : 12417024
# Available bytes        : 12417054
# input_dir ='/home/jbowden/APPN/repos/phenomate_data/Amiga/UM_Tests/raw/um_test_1/'
# input_file ="2026-02-10_12-31-49_829651_+1030_test-jai1.bin"
input_name = input_dir + input_file
print(f'input_name: {input_name} ')
 
output_dir = '/home/jbowden/APPN/temp/jai_output/'

preproc = JaiPreprocessor(path=input_name)
preproc.extract()
preproc.save(path=output_dir)

# cd /home/jbowden/APPN/repos/phenomate-core ; /usr/bin/env /home/jbowden/APPN/repos/APPN_GenricFileStorage/.venv/bin/python /home/jbowden/.vscode/extensions/ms-python.debugpy-2025.18.0-linux-x64/bundled/libs/debugpy/adapter/../../debugpy/launcher 59107 -- /home/jbowden/APPN/repos/phenomate-core/tests/test_jai.py 
# JaiPreprocessor.extract(): First 35 bytes of serialized image: 0a80f0f5051c1e1b1c191a1b1c1c1d1d1f1d1c191e1e1f1d1a191f1b201c1e1d1e1a1e
# JaiPreprocessor.extract(): First 35 bytes of serialized image: 0a80f0f5051b1c191a191b1b1e1b1f1b1d1d1d1d1f1d1d1a1c1a1e1e1f1c1f1c1e1a1b
# JaiPreprocessor.extract(): First 35 bytes of serialized image: 0a80f0f5051d1b1b1c1a1c1a1d1a1d1b1e1a1d1a1c1c1b1b1d1a1c1f1e1d211d1d1c1b
# JaiPreprocessor.extract(): First 35 bytes of serialized image: 0a80f0f5051b1e191c191a1b1d191e191c1d1d1b1d1b1b1a1b1b1c1d1f1f1f1c201c1d
# JaiPreprocessor.extract(): First 35 bytes of serialized image: 0a80f0f5051b1e191a1b1b1e1b1d1d1b1e1d1e1a1d1a1e1d1b1c201d1d1d1e1d1c1f1c
# JaiPreprocessor.extract(): First 35 bytes of serialized image: 0a80f0f5051a1c191b181a19191a1e1d1c1d1f1b1e1c1c1a1a1a1d1d1f1b1d1a1d1b1d
# JaiPreprocessor.extract(): First 35 bytes of serialized image: 0a80f0f5051c1d1a1a191a1b1d1d1c1d1d1d1c1a1d1c1c1c1c191f1b1d191d1a1d1c1a
# JaiPreprocessor.extract(): First 35 bytes of serialized image: 0a80f0f5051a1d1d1a1b1d1a1c1a1b1c1e1c1e1b1d1b1c181c1c1f1f1c1d1e1c1d1d1f

# 0x80 -> 0
# 0xF0 -> 0x70 << 7 = 112 << 7 = 14,336
# 0xF5 -> 0x75 << 14 = 117 << 14 = 1,916,928
# 0x05 -> 5 << 21 = 10,485,760
# --------------------------------
# total length = 12,417,024 bytes

# import binascii

# def decode_varint(b, start=0):
    # shift = 0
    # value = 0
    # i = start
    # while True:
        # byte = b[i]
        # value |= (byte & 0x7F) << shift
        # i += 1
        # if (byte & 0x80) == 0:
            # break
        # shift += 7
    # return value, i

# raw = bytes.fromhex("0a80f0f5051c1e1b...")  # any of your lines
# assert raw[0] == 0x0A  # field 1, length-delimited
# length, after = decode_varint(raw, 1)
# print("Declared length:", length)  # should print 12417024
# print("Available bytes:", len(raw) - after)


