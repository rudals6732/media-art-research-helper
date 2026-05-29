package com.project.model;

import java.util.List;

public class ReportSection {
    public enum SectionType { INTRO, BODY, CONCLUSION, REFERENCES }

    private SectionType type;
    private String heading;
    private String content;
    private List<String> citationIds; // Paper IDs cited in this section

    public ReportSection() {}

    public ReportSection(SectionType type, String heading, String content, List<String> citationIds) {
        this.type = type;
        this.heading = heading;
        this.content = content;
        this.citationIds = citationIds;
    }

    public SectionType getType() { return type; }
    public void setType(SectionType type) { this.type = type; }

    public String getHeading() { return heading; }
    public void setHeading(String heading) { this.heading = heading; }

    public String getContent() { return content; }
    public void setContent(String content) { this.content = content; }

    public List<String> getCitationIds() { return citationIds; }
    public void setCitationIds(List<String> citationIds) { this.citationIds = citationIds; }
}
