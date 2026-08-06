package com.echoes.user.domain.user.repository.typehandler;

import com.echoes.user.domain.user.enums.UserType;
import org.apache.ibatis.type.BaseTypeHandler;
import org.apache.ibatis.type.JdbcType;

import java.sql.*;

/**
 * MyBatis TypeHandler for mapping DB string value to UserType enum.
 * Read: DB value (string: elder/child/normal) -> UserType
 * Write: UserType -> DB value (use name as string)
 */
public class UserTypeHandler extends BaseTypeHandler<UserType> {

    @Override
    public void setNonNullParameter(PreparedStatement ps, int i, UserType parameter, JdbcType jdbcType) throws SQLException {
        ps.setString(i, parameter == null ? null : parameter.name().toLowerCase());
    }

    @Override
    public UserType getNullableResult(ResultSet rs, String columnName) throws SQLException {
        String name = rs.getString(columnName);
        return rs.wasNull() ? null : UserType.fromName(name);
    }

    @Override
    public UserType getNullableResult(ResultSet rs, int columnIndex) throws SQLException {
        String name = rs.getString(columnIndex);
        return rs.wasNull() ? null : UserType.fromName(name);
    }

    @Override
    public UserType getNullableResult(CallableStatement cs, int columnIndex) throws SQLException {
        String name = cs.getString(columnIndex);
        return cs.wasNull() ? null : UserType.fromName(name);
    }
}
