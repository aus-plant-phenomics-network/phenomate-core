from pathlib import Path
from phenomate_core.preprocessing.lidar2d import lidar_pb2
import sys
import os

import ctypes 
import datetime

import phenomate_core.preprocessing.lidar2d.sick_scan_api as ss

def from_proto(protocol_message):

    header = ss.SickScanHeader(
        seq=protocol_message.header.seq,
        timestamp_sec=protocol_message.header.timestamp_sec,
        timestamp_nsec=protocol_message.header.timestamp_nsec,
        frame_id=protocol_message.header.frame_id,
    )

    num_fields = protocol_message.fields.size
    array = ss.SickScanPointFieldMsg * num_fields
    elements = array()

    for n in range(num_fields):
        field = ss.SickScanPointFieldMsg(
            name=protocol_message.fields.buffer[n].name,
            offset=protocol_message.fields.buffer[n].offset,
            datatype=protocol_message.fields.buffer[n].datatype,
            count=protocol_message.fields.buffer[n].count,
        )
        elements[n] = field

    fields = ss.SickScanPointFieldArray(
        capacity=protocol_message.fields.capacity,
        size=protocol_message.fields.size,
        buffer=elements,
    )

    byte_data = bytes(protocol_message.data.buffer)
    size = len(byte_data)
    buffer_copy = bytearray(byte_data)
    buffer_type = ctypes.c_uint8 * size
    buffer_instance = buffer_type.from_buffer(buffer_copy)
    # print(f"Buffer size is {size}")

    data = ss.SickScanUint8Array(
        capacity=protocol_message.data.capacity,
        size=protocol_message.data.size,
        buffer=buffer_instance,
    )

    message_contents = ss.SickScanPointCloudMsg(
        header=header,
        height=protocol_message.height,
        width=protocol_message.width,
        fields=fields,
        is_bigendian=protocol_message.is_bigendian,
        point_step=protocol_message.point_step,
        row_step=protocol_message.row_step,
        data=data,
        is_dense=protocol_message.is_dense,
        num_echos=protocol_message.num_echos,
        segment_idx=protocol_message.segment_idx,
    )

    return message_contents

