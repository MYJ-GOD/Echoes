package com.echoes.voice.domain.voice.repository.typehandler;

import org.apache.ibatis.type.JdbcType;
import org.apache.ibatis.type.MappedJdbcTypes;
import org.apache.ibatis.type.MappedTypes;
import org.apache.ibatis.type.TypeHandler;

import java.nio.ByteBuffer;
import java.sql.*;
import java.util.UUID;

@MappedJdbcTypes(JdbcType.BINARY)
@MappedTypes(UUID.class)
public class UUIDTypeHandler implements TypeHandler<UUID> {

    @Override
    public void setParameter(PreparedStatement ps, int i, UUID parameter, JdbcType jdbcType) throws SQLException {
        if (parameter == null) {
            ps.setNull(i, Types.VARBINARY);
        } else {
            ByteBuffer bb = ByteBuffer.allocate(16);
            bb.putLong(parameter.getMostSignificantBits());
            bb.putLong(parameter.getLeastSignificantBits());
            ps.setBytes(i, bb.array());
        }
    }

    @Override
    public UUID getResult(ResultSet rs, String columnName) throws SQLException {
        byte[] bytes = rs.getBytes(columnName);
        return bytesToUuid(bytes);
    }

    @Override
    public UUID getResult(ResultSet rs, int columnIndex) throws SQLException {
        byte[] bytes = rs.getBytes(columnIndex);
        return bytesToUuid(bytes);
    }

    @Override
    public UUID getResult(CallableStatement cs, int columnIndex) throws SQLException {
        byte[] bytes = cs.getBytes(columnIndex);
        return bytesToUuid(bytes);
    }

    private UUID bytesToUuid(byte[] bytes) {
        if (bytes == null) {
            return null;
        }
        ByteBuffer bb = ByteBuffer.wrap(bytes);
        long high = bb.getLong();
        long low = bb.getLong();
        return new UUID(high, low);
    }
}
